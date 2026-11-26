package com.microservices_example_app.gateway;

import com.microservices_example_app.gateway.filter.JwtAuthenticationGlobalFilter;
import com.microservices_example_app.gateway.filter.RouteValidator;
import com.microservices_example_app.gateway.utils.JwtUtil;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.reactive.server.WebTestClient;
import reactor.core.publisher.Mono;

class JwtFilterProblemDetailTest {

    private WebTestClient clientFor(JwtAuthenticationGlobalFilter filter) {
        return WebTestClient.bindToWebHandler(exchange ->
                filter.filter(exchange, e -> {
                    e.getResponse().setStatusCode(HttpStatus.OK);
                    return e.getResponse().setComplete();
                })).build();
    }

    private JwtAuthenticationGlobalFilter filter() {
        return new JwtAuthenticationGlobalFilter(
                new RouteValidator(),
                new JwtUtil("test-secret-key-at-least-32-chars-long!!"));
    }

    @Test
    void missingAuthHeaderReturnsProblemDetail() {
        clientFor(filter()).get().uri("/users/profile")
                .exchange()
                .expectStatus().isUnauthorized()
                .expectHeader().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON)
                .expectBody()
                .jsonPath("$.type").isEqualTo("https://dosug.example/problems/unauthorized")
                .jsonPath("$.status").isEqualTo(401)
                .jsonPath("$.detail").isEqualTo("Authorization header is missing or invalid")
                .jsonPath("$.code").isEqualTo("unauthorized")
                .jsonPath("$.traceId").isNotEmpty()
                .jsonPath("$.title").isNotEmpty();
    }

    @Test
    void invalidTokenReturnsProblemDetail() {
        clientFor(filter()).get().uri("/users/profile")
                .header("Authorization", "Bearer invalid-token")
                .exchange()
                .expectStatus().isUnauthorized()
                .expectHeader().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON)
                .expectBody()
                .jsonPath("$.code").isEqualTo("unauthorized")
                .jsonPath("$.detail").isEqualTo("Invalid or expired token");
    }

    @Test
    void unauthorizedEchoesRequestIdHeader() {
        clientFor(filter()).get().uri("/users/profile")
                .header("X-Request-ID", "req-abc")
                .exchange()
                .expectStatus().isUnauthorized()
                .expectBody()
                .jsonPath("$.traceId").isEqualTo("req-abc");
    }

    @Test
    void openEndpointPassesThrough() {
        clientFor(filter()).post().uri("/users/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .body(Mono.just("{}"), String.class)
                .exchange()
                .expectStatus().isOk();
    }
}
