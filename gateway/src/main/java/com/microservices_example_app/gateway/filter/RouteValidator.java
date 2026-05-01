package com.microservices_example_app.gateway.filter;

import lombok.extern.slf4j.Slf4j;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.function.Predicate;

@Component
@Slf4j
public class RouteValidator {


    private static final List<String> OPEN_API_ENDPOINTS = List.of(
            "/users/auth/login",
            "/users/auth/register",
            "/actuator/health",
            "/users/auth/forget-password",
            "/users/auth/reset-password",
            "/users/auth/validate-reset-token"
    );

    public final Predicate<ServerHttpRequest> isSecured =
            request -> {
                String path = request.getURI().getPath();
                boolean isOpen = OPEN_API_ENDPOINTS.stream()
                        .anyMatch(uri -> path.startsWith(uri));
                log.info("RouteValidator: path={}, isOpenEndpoint={}, isSecured={}", path, isOpen, !isOpen);
                return OPEN_API_ENDPOINTS.stream()
                        .noneMatch(uri -> path.startsWith(uri));
            };
}