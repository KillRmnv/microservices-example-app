package com.microservices_example_app.gateway.filter;

import lombok.extern.slf4j.Slf4j;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

@Component
@Slf4j
public class LoggingGlobalFilter implements GlobalFilter, Ordered {



    @Override
    public Mono<Void> filter(ServerWebExchange exchange, org.springframework.cloud.gateway.filter.GatewayFilterChain chain) {
        String path = exchange.getRequest().getURI().getPath();
        String method = exchange.getRequest().getMethod().name();
        
        log.info("                      GATEWAY REQUEST                      ");
        log.info("Method: {}, Path: {}", method, path);
        log.info("Headers: {}", exchange.getRequest().getHeaders());
        
        return chain.filter(exchange).then(
                Mono.fromRunnable(() -> {
                    log.info("                      GATEWAY RESPONSE                      ");
                    log.info("Status: {}", exchange.getResponse().getStatusCode());
                })
        );
    }

    @Override
    public int getOrder() {
        return -2; // Execute before JwtAuthenticationGlobalFilter (-1)
    }
}
