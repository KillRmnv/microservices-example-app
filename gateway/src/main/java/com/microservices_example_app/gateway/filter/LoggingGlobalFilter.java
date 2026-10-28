package com.microservices_example_app.gateway.filter;

import lombok.extern.slf4j.Slf4j;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.util.UUID;

@Component
@Slf4j
public class LoggingGlobalFilter implements GlobalFilter, Ordered {

    public static final String REQUEST_ID_HEADER = "X-Request-ID";

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        long start = System.currentTimeMillis();
        ServerHttpRequest request = exchange.getRequest();
        String method = request.getMethod().name();
        String path = request.getURI().getPath();

        String requestId = request.getHeaders().getFirst(REQUEST_ID_HEADER);
        if (requestId == null || requestId.isBlank()) {
            requestId = UUID.randomUUID().toString();
        }
        final String finalRequestId = requestId;

        ServerWebExchange outbound = exchange;
        if (request.getHeaders().getFirst(REQUEST_ID_HEADER) == null) {
            ServerHttpRequest mutated = request.mutate()
                    .header(REQUEST_ID_HEADER, finalRequestId)
                    .build();
            outbound = exchange.mutate().request(mutated).build();
        }
        // Echo back to the caller; set before the response commits.
        outbound.getResponse().getHeaders().set(REQUEST_ID_HEADER, finalRequestId);

        log.atInfo()
                .addKeyValue("requestId", finalRequestId)
                .addKeyValue("method", method)
                .addKeyValue("path", path)
                .log("Gateway request");

        final ServerWebExchange finalOutbound = outbound;
        return chain.filter(finalOutbound).then(
                Mono.fromRunnable(() -> {
                    long durationMs = System.currentTimeMillis() - start;
                    Object status = finalOutbound.getResponse().getStatusCode();
                    log.atInfo()
                            .addKeyValue("requestId", finalRequestId)
                            .addKeyValue("method", method)
                            .addKeyValue("path", path)
                            .addKeyValue("status", status != null ? status.toString() : "unknown")
                            .addKeyValue("durationMs", durationMs)
                            .log("Gateway response");
                })
        );
    }

    @Override
    public int getOrder() {
        return -2; // Execute before JwtAuthenticationGlobalFilter (-1)
    }
}
