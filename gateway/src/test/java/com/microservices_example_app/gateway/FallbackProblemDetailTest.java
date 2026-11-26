package com.microservices_example_app.gateway;

import com.microservices_example_app.gateway.controller.FallbackController;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.reactive.server.WebTestClient;

class FallbackProblemDetailTest {

    private final WebTestClient client =
            WebTestClient.bindToController(new FallbackController()).build();

    @Test
    void usersFallbackReturnsProblemDetail() {
        client.get().uri("/fallback/users")
                .exchange()
                .expectStatus().isEqualTo(503)
                .expectHeader().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON)
                .expectBody()
                .jsonPath("$.type").isEqualTo("https://dosug.example/problems/users_unavailable")
                .jsonPath("$.status").isEqualTo(503)
                .jsonPath("$.detail").isEqualTo("Users service is temporarily unavailable")
                .jsonPath("$.code").isEqualTo("users_unavailable")
                .jsonPath("$.traceId").isNotEmpty()
                .jsonPath("$.title").isNotEmpty();
    }

    @Test
    void bookingFallbackReturnsProblemDetail() {
        client.get().uri("/fallback/booking")
                .exchange()
                .expectStatus().isEqualTo(503)
                .expectHeader().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON)
                .expectBody()
                .jsonPath("$.type").isEqualTo("https://dosug.example/problems/booking_unavailable")
                .jsonPath("$.code").isEqualTo("booking_unavailable")
                .jsonPath("$.status").isEqualTo(503)
                .jsonPath("$.traceId").isNotEmpty();
    }

    @Test
    void assistantFallbackReturnsProblemDetail() {
        client.get().uri("/fallback/assistant")
                .exchange()
                .expectStatus().isEqualTo(503)
                .expectHeader().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON)
                .expectBody()
                .jsonPath("$.type").isEqualTo("https://dosug.example/problems/assistant_unavailable")
                .jsonPath("$.code").isEqualTo("assistant_unavailable")
                .jsonPath("$.status").isEqualTo(503)
                .jsonPath("$.traceId").isNotEmpty();
    }

    @Test
    void fallbackEchoesRequestIdHeader() {
        client.get().uri("/fallback/users")
                .header("X-Request-ID", "req-789")
                .exchange()
                .expectStatus().isEqualTo(503)
                .expectBody()
                .jsonPath("$.traceId").isEqualTo("req-789");
    }
}
