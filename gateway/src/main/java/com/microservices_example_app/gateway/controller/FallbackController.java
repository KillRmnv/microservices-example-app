package com.microservices_example_app.gateway.controller;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.web.bind.annotation.*;
import lombok.extern.slf4j.Slf4j;

import java.net.URI;
import java.util.UUID;

@Slf4j
@RestController
@RequestMapping("/fallback")
@Tag(name = "Fallbacks", description = "Circuit-breaker fallback responses (excluded from the public schema)")
public class FallbackController {

    private static final String TYPE_BASE = "https://dosug.example/problems/";

    private static ProblemDetail unavailable(String code, String detail, ServerHttpRequest request) {
        ProblemDetail pd = ProblemDetail.forStatusAndDetail(
                HttpStatus.SERVICE_UNAVAILABLE, detail);
        pd.setType(URI.create(TYPE_BASE + code));
        pd.setTitle(HttpStatus.SERVICE_UNAVAILABLE.getReasonPhrase());
        pd.setInstance(URI.create(request != null ? request.getPath().value() : "/"));
        pd.setProperty("code", code);
        pd.setProperty("traceId", resolveTraceId(request));
        return pd;
    }

    private static String resolveTraceId(ServerHttpRequest request) {
        if (request != null) {
            String header = request.getHeaders().getFirst("X-Request-ID");
            if (header != null && !header.isBlank()) {
                return header;
            }
        }
        return UUID.randomUUID().toString();
    }

    @Operation(summary = "Fallback when the user service is unavailable")
    @RequestMapping("/users")
    public ResponseEntity<ProblemDetail> usersFallback(ServerHttpRequest request) {
        log.warn("Users service is unavailable, triggering fallback");
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                .body(unavailable("users_unavailable",
                        "Users service is temporarily unavailable", request));
    }

    @Operation(summary = "Fallback when the booking service is unavailable")
    @RequestMapping("/booking")
    public ResponseEntity<ProblemDetail> bookingFallback(ServerHttpRequest request) {
        log.warn("Booking service is unavailable, triggering fallback");
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                .body(unavailable("booking_unavailable",
                        "Booking service is temporarily unavailable", request));
    }

    @Operation(summary = "Fallback when the assistant service is unavailable")
    @RequestMapping("/assistant")
    public ResponseEntity<ProblemDetail> assistantFallback(ServerHttpRequest request) {
        log.warn("Assistant service is unavailable, triggering fallback");
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                .body(unavailable("assistant_unavailable",
                        "Assistant service is temporarily unavailable", request));
    }
}
