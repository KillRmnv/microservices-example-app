package com.microservices_example_app.booking;

import com.microservices_example_app.booking.dto.TicketCreateRequestDto;
import com.microservices_example_app.booking.model.Zone;
import com.microservices_example_app.booking.producers.NotificationKafkaBookingProducer;
import com.microservices_example_app.booking.service.TicketService;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;
import org.springframework.web.server.ResponseStatusException;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import javax.crypto.SecretKey;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("concurrency")
@SpringBootTest(properties = "booking.catalog.publish-on-startup=false")
@Testcontainers
class TicketCapacityConcurrencyTest {

    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:latest");

    @Container
    static GenericContainer<?> redis =
            new GenericContainer<>(DockerImageName.parse("redis:latest"))
                    .withExposedPorts(6379);

    @DynamicPropertySource
    static void redisProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.data.redis.host", redis::getHost);
        registry.add("spring.data.redis.port", () -> redis.getMappedPort(6379));
    }

    private static final String JWT = token();
    private static final int CAPACITY = 5;

    @MockitoBean
    private NotificationKafkaBookingProducer bookingProducer;

    @Autowired
    private TicketService service;

    @Autowired
    private JdbcTemplate jdbc;

    private Long eventId;
    private Long venueId;

    @BeforeEach
    void setUp() {
        Long townId = jdbc.queryForObject(
                "SELECT id FROM towns WHERE name = 'Minsk'", Long.class);
        venueId = jdbc.queryForObject(
                "INSERT INTO venues (town_id, place, capacity) "
                        + "VALUES (?, 'Race Capacity Hall', ?) RETURNING id",
                Long.class, townId, CAPACITY);
        eventId = jdbc.queryForObject(
                "INSERT INTO events (title, starts_at, ends_at, venue_id, "
                        + "category, admission_mode) VALUES "
                        + "('Race General Admission', now() + interval '1 day', "
                        + "now() + interval '1 day 2 hours', ?, 'concert', 'GENERAL') "
                        + "RETURNING id",
                Long.class, venueId);
    }

    @AfterEach
    void tearDown() {
        jdbc.update("DELETE FROM tickets WHERE event_id = ?", eventId);
        jdbc.update("DELETE FROM events WHERE id = ?", eventId);
        jdbc.update("DELETE FROM venues WHERE id = ?", venueId);
    }

    @Test
    void parallel_general_admission_never_exceeds_venue_capacity() throws Exception {
        int workers = 10;
        CountDownLatch ready = new CountDownLatch(workers);
        CountDownLatch start = new CountDownLatch(1);
        AtomicInteger created = new AtomicInteger();
        AtomicInteger rejected = new AtomicInteger();
        List<Throwable> unexpected = new ArrayList<>();
        ExecutorService pool = Executors.newFixedThreadPool(workers);

        try {
            List<Future<?>> futures = new ArrayList<>();
            for (int i = 0; i < workers; i++) {
                futures.add(pool.submit(() -> {
                    ready.countDown();
                    try {
                        start.await(10, TimeUnit.SECONDS);
                        withRequest(() -> {
                            service.create(request());
                            return null;
                        });
                        created.incrementAndGet();
                    } catch (ResponseStatusException exc) {
                        if (exc.getStatusCode().value() == 409) {
                            rejected.incrementAndGet();
                        } else {
                            synchronized (unexpected) {
                                unexpected.add(exc);
                            }
                        }
                    } catch (Throwable exc) {
                        synchronized (unexpected) {
                            unexpected.add(exc);
                        }
                    }
                }));
            }
            ready.await(10, TimeUnit.SECONDS);
            start.countDown();
            for (Future<?> future : futures) {
                future.get(30, TimeUnit.SECONDS);
            }
        } finally {
            pool.shutdownNow();
        }

        assertThat(unexpected).isEmpty();
        assertThat(created.get()).isEqualTo(CAPACITY);
        assertThat(rejected.get()).isEqualTo(workers - CAPACITY);
        Integer active = jdbc.queryForObject(
                "SELECT count(*) FROM tickets WHERE event_id = ? AND active",
                Integer.class, eventId);
        assertThat(active).isEqualTo(CAPACITY);
    }

    private TicketCreateRequestDto request() {
        TicketCreateRequestDto request = new TicketCreateRequestDto();
        request.setEventId(eventId);
        request.setZone(Zone.BASIC);
        request.setPrice(BigDecimal.valueOf(50));
        request.setActive(true);
        return request;
    }

    private <T> T withRequest(java.util.concurrent.Callable<T> action)
            throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.addHeader("Authorization", "Bearer " + JWT);
        RequestContextHolder.setRequestAttributes(
                new ServletRequestAttributes(request));
        try {
            return action.call();
        } finally {
            RequestContextHolder.resetRequestAttributes();
        }
    }

    private static String token() {
        SecretKey key = Keys.hmacShaKeyFor(
                "your-super-secret-key-at-least-32-characters-long!"
                        .getBytes(StandardCharsets.UTF_8));
        return Jwts.builder()
                .subject("race")
                .claim("id", 77L)
                .claim("email", "race@example.com")
                .signWith(key)
                .compact();
    }
}
