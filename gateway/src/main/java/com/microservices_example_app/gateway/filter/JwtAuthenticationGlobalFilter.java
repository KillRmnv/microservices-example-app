package com.microservices_example_app.gateway.filter;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.microservices_example_app.gateway.filter.RouteValidator;
import com.microservices_example_app.gateway.utils.JwtUtil;
import io.jsonwebtoken.Claims;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.Ordered;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.stereotype.Component;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

@Component
@Slf4j
public class JwtAuthenticationGlobalFilter implements GlobalFilter, Ordered {

    private final RouteValidator routeValidator;
    private final JwtUtil jwtUtil;

    public JwtAuthenticationGlobalFilter(RouteValidator routeValidator, JwtUtil jwtUtil) {
        this.routeValidator = routeValidator;
        this.jwtUtil = jwtUtil;
    }



    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();
        String path = request.getURI().getPath();
        String method = request.getMethod().name();
        log.info("Incoming request: {} {}", method, path);

        if (!routeValidator.isSecured.test(request)) {
            log.info("Request {} is NOT secured, skipping JWT check", path);
            return chain.filter(exchange);
        }
        log.info("Request {} IS secured, validating JWT", path);

        String authHeader = request.getHeaders().getFirst(HttpHeaders.AUTHORIZATION);

        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            return unauthorized(exchange, "Authorization header is missing or invalid");
        }

        String token = authHeader.substring(7);

        if (!jwtUtil.validateToken(token)) {
            return unauthorized(exchange, "Invalid or expired token");
        }

        Claims claims = jwtUtil.parseToken(token);
        String username = claims.getSubject();
        String role = claims.get("role", String.class);
        String email = claims.get("email", String.class);

        ServerHttpRequest mutatedRequest = request.mutate()
                .headers(headers -> {
                    headers.remove("X-User-Name");
                    headers.remove("X-User-Role");
                    headers.remove("X-User-Email");
                })
                .header("X-User-Name", username != null ? username : "")
                .header("X-User-Role", role != null ? role : "")
                .header("X-User-Email", email != null ? email : "")
                .build();

        return chain.filter(exchange.mutate().request(mutatedRequest).build());
    }

    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();

    private Mono<Void> unauthorized(ServerWebExchange exchange, String message) {
        exchange.getResponse().setStatusCode(HttpStatus.UNAUTHORIZED);
        exchange.getResponse().getHeaders().setContentType(MediaType.APPLICATION_PROBLEM_JSON);

        ServerHttpRequest request = exchange.getRequest();
        String incomingTraceId = request.getHeaders().getFirst("X-Request-ID");
        String traceId = (incomingTraceId != null && !incomingTraceId.isBlank())
                ? incomingTraceId : UUID.randomUUID().toString();

        // Build the RFC 9457 body explicitly: a plain ObjectMapper does not apply
        // Spring's ProblemDetail Jackson mixin, so serializing ProblemDetail
        // directly would nest custom properties under "properties".
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("type", "https://dosug.example/problems/unauthorized");
        body.put("title", HttpStatus.UNAUTHORIZED.getReasonPhrase());
        body.put("status", HttpStatus.UNAUTHORIZED.value());
        body.put("detail", message);
        body.put("instance", request.getPath().value());
        body.put("code", "unauthorized");
        body.put("traceId", traceId);

        byte[] bytes;
        try {
            bytes = OBJECT_MAPPER.writeValueAsBytes(body);
        } catch (Exception e) {
            log.error("Failed to serialize ProblemDetail", e);
            bytes = ("{\"type\":\"https://dosug.example/problems/unauthorized\","
                    + "\"title\":\"Unauthorized\",\"status\":401,\"detail\":\"Unauthorized\","
                    + "\"code\":\"unauthorized\",\"traceId\":\"" + traceId + "\"}")
                    .getBytes(StandardCharsets.UTF_8);
        }

        DataBuffer buffer = exchange.getResponse()
                .bufferFactory()
                .wrap(bytes);

        return exchange.getResponse().writeWith(Mono.just(buffer));
    }

    @Override
    public int getOrder() {
        return -1;
    }
}