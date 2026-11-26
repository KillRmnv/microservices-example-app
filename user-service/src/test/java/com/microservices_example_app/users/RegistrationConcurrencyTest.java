package com.microservices_example_app.users;

import com.microservices_example_app.users.producers.NotificationKafkaAuthenticationProducer;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

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
@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = {
                "spring.kafka.listener.auto-startup=false",
                "SPRING_KAFKA_BOOTSTRAP_SERVERS=localhost:9092",
                "USER_APPLICATION_NAME=user-service",
                "USER_APPLICATION_ADDRESS=0.0.0.0",
                "USER_APPLICATION_PORT=0",
                "RESTORE_PASSWORD_URL=http://localhost/reset-password",
                "ADMIN_USERNAME=admin",
                "ADMIN_MAIL=admin@example.com",
                "ADMIN_PASSWORD=admin-secret",
                "SPRINGDOC_API_DOCS_ENABLED=false",
                "SPRINGDOC_SWAGGER_UI_ENABLED=false"
        })
@Testcontainers
class RegistrationConcurrencyTest {

    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:latest");

    @DynamicPropertySource
    static void databaseProperties(DynamicPropertyRegistry registry) {
        registry.add("USER_DATASOURCE_URL", postgres::getJdbcUrl);
        registry.add("USER_DATASOURCE_USERNAME", postgres::getUsername);
        registry.add("USER_DATASOURCE_PASSWORD", postgres::getPassword);
        registry.add("USER_MIGRATION_URL", postgres::getJdbcUrl);
    }

    @MockitoBean
    private NotificationKafkaAuthenticationProducer authenticationProducer;

    @LocalServerPort
    private int port;

    private static final HttpClient CLIENT = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    @Autowired
    private JdbcTemplate jdbc;

    private static final String EMAIL = "race-register@example.com";
    private static final String USERNAME = "race-register";

    @BeforeEach
    void cleanUp() {
        jdbc.update("DELETE FROM users WHERE email = ? OR username = ?",
                EMAIL, USERNAME);
    }

    @Test
    void parallel_registrations_create_one_user_and_one_conflict() throws Exception {
        int workers = 6;
        CountDownLatch ready = new CountDownLatch(workers);
        CountDownLatch start = new CountDownLatch(1);
        AtomicInteger ok = new AtomicInteger();
        AtomicInteger conflict = new AtomicInteger();
        List<Throwable> unexpected = new ArrayList<>();
        ExecutorService pool = Executors.newFixedThreadPool(workers);

        try {
            List<Future<?>> futures = new ArrayList<>();
            for (int i = 0; i < workers; i++) {
                futures.add(pool.submit(() -> {
                    ready.countDown();
                    try {
                        start.await(10, TimeUnit.SECONDS);
                        HttpResponse<String> response = register();
                        if (response.statusCode() == 200) {
                            ok.incrementAndGet();
                        } else if (response.statusCode() == 409) {
                            conflict.incrementAndGet();
                        } else {
                            synchronized (unexpected) {
                                unexpected.add(new AssertionError(
                                        "unexpected status " + response.statusCode()
                                                + ": " + response.body()));
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
        assertThat(ok.get()).isEqualTo(1);
        assertThat(conflict.get()).isEqualTo(workers - 1);
        Integer users = jdbc.queryForObject(
                "SELECT count(*) FROM users WHERE email = ?", Integer.class, EMAIL);
        assertThat(users).isEqualTo(1);
    }

    private HttpResponse<String> register() throws Exception {
        String body = "{\"email\":\"" + EMAIL + "\","
                + "\"username\":\"" + USERNAME + "\","
                + "\"password\":\"secret123\","
                + "\"role\":\"CUSTOMER\","
                + "\"isSystem\":false}";
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create("http://localhost:" + port + "/users/auth/register"))
                .timeout(Duration.ofSeconds(20))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();
        return CLIENT.send(request, HttpResponse.BodyHandlers.ofString());
    }
}