package com.microservices_example_app.booking;

import com.microservices_example_app.booking.dto.SeatableTicketCreateRequestDto;
import com.microservices_example_app.booking.model.Zone;
import com.microservices_example_app.booking.producers.NotificationKafkaBookingProducer;
import com.microservices_example_app.booking.service.SeatableTicketService;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.ConcurrencyFailureException;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.web.server.ResponseStatusException;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import javax.crypto.SecretKey;
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
class SeatableTicketConcurrencyTest {

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

    @MockitoBean
    private NotificationKafkaBookingProducer bookingProducer;

    @Autowired
    private SeatableTicketService service;

    @Autowired
    private JdbcTemplate jdbc;

    private Long eventId;
    private Long seatId;

    @BeforeEach
    void setUp() {
        eventId = jdbc.queryForObject(
                "SELECT id FROM events WHERE title = 'Imagine Dragons Tribute'",
                Long.class);
        seatId = jdbc.queryForObject(
                "SELECT s.id FROM seats s JOIN events e ON e.venue_id = s.venue_id "
                        + "WHERE e.id = ? ORDER BY s.id LIMIT 1",
                Long.class, eventId);
        jdbc.update("DELETE FROM tickets WHERE event_id = ?", eventId);
    }

    @AfterEach
    void tearDown() {
        jdbc.update("DELETE FROM tickets WHERE event_id = ?", eventId);
    }

    @Test
    void parallel_bookings_of_one_seat_produce_one_ticket() throws Exception {
        int workers = 8;
        CountDownLatch ready = new CountDownLatch(workers);
        CountDownLatch start = new CountDownLatch(1);
        AtomicInteger created = new AtomicInteger();
        AtomicInteger conflicts = new AtomicInteger();
        List<Throwable> unexpected = new ArrayList<>();
        ExecutorService pool = Executors.newFixedThreadPool(workers);

        try {
            List<Future<?>> futures = new ArrayList<>();
            for (int i = 0; i < workers; i++) {
                futures.add(pool.submit(() -> {
                    ready.countDown();
                    try {
                        start.await(10, TimeUnit.SECONDS);
                        MockHttpServletRequest request = new MockHttpServletRequest();
                        request.addHeader("Authorization", "Bearer " + JWT);
                        RequestContextHolder.setRequestAttributes(
                                new ServletRequestAttributes(request));
                        service.create(request());
                        created.incrementAndGet();
                    } catch (ResponseStatusException exc) {
                        if (exc.getStatusCode().value() == 409) {
                            conflicts.incrementAndGet();
                        } else {
                            synchronized (unexpected) {
                                unexpected.add(exc);
                            }
                        }
                    } catch (ConcurrencyFailureException exc) {
                        // A lock/transaction conflict means the create lost the race.
                        conflicts.incrementAndGet();
                    } catch (Throwable exc) {
                        synchronized (unexpected) {
                            unexpected.add(exc);
                        }
                    } finally {
                        RequestContextHolder.resetRequestAttributes();
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
        assertThat(created.get()).isEqualTo(1);
        assertThat(conflicts.get()).isEqualTo(workers - 1);
        Integer active = jdbc.queryForObject(
                "SELECT count(*) FROM tickets t JOIN seatable_tickets st "
                        + "ON st.ticket_id = t.id WHERE t.event_id = ? AND t.active",
                Integer.class, eventId);
        assertThat(active).isEqualTo(1);
    }

    private SeatableTicketCreateRequestDto request() {
        SeatableTicketCreateRequestDto request = new SeatableTicketCreateRequestDto();
        request.setEventId(eventId);
        request.setSeatId(seatId);
        request.setZone(Zone.VIP);
        request.setPrice(BigDecimal.valueOf(250));
        request.setActive(true);
        return request;
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

    @Test
    void parallel_refunds_apply_once() throws Exception {
        Long ticketId = withRequest(() -> service.create(request()).getId());
        int workers = 6;
        CountDownLatch ready = new CountDownLatch(workers);
        CountDownLatch start = new CountDownLatch(1);
        AtomicInteger refunded = new AtomicInteger();
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
                            service.refund(ticketId);
                            return null;
                        });
                        refunded.incrementAndGet();
                    } catch (IllegalArgumentException exc) {
                        rejected.incrementAndGet();
                    } catch (ConcurrencyFailureException exc) {
                        // A lock/transaction conflict means the refund did not apply.
                        rejected.incrementAndGet();
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
        assertThat(refunded.get()).isEqualTo(1);
        assertThat(rejected.get()).isEqualTo(workers - 1);
        Boolean active = jdbc.queryForObject(
                "SELECT active FROM tickets WHERE id = ?", Boolean.class, ticketId);
        assertThat(active).isFalse();
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
}
