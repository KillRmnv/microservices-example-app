package com.microservices_example_app.gateway.filter;

import lombok.extern.slf4j.Slf4j;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpMethod;
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

    private static final List<String> OPEN_API_PREFIXES = List.of(
            "/v3/api-docs",
            "/swagger-ui",
            "/webjars/",
            "/swagger-resources"
    );

    /**
     * Public read-only catalog: browsing the playbill and venues must work
     * without an account. Mutations stay behind the JWT (method check), and
     * the mirrored collector catalog is opened explicitly.
     */
    /**
     * Read-only POSTs: hybrid search and dialogue turns are stateless and
     * must work for anonymous visitors. Holds/mutations stay secured.
     * /assistant/plan is explicit and reasoning-backed (may take minutes),
     * but equally stateless.
     */
    private static final List<String> PUBLIC_POST_PATHS = List.of(
            "/assistant/search",
            "/assistant/search_venues",
            "/assistant/dialogue",
            "/assistant/dialogue/v2",
            "/assistant/query",
            "/assistant/plan"
    );

    private static final List<String> PUBLIC_GET_PREFIXES = List.of(
            "/catalog/",
            "/booking/events",
            "/booking/venues",
            "/booking/towns",
            "/booking/tickets/search",
            "/booking/seatable-tickets/search",
            "/booking/seats"
    );

    public final Predicate<ServerHttpRequest> isSecured =
            request -> {
                String path = request.getURI().getPath();
                boolean isOpen = OPEN_API_ENDPOINTS.contains(path)
                        || OPEN_API_PREFIXES.stream().anyMatch(path::startsWith)
                        || (HttpMethod.GET.equals(request.getMethod())
                            && PUBLIC_GET_PREFIXES.stream().anyMatch(path::startsWith))
                        || (HttpMethod.POST.equals(request.getMethod())
                            && PUBLIC_POST_PATHS.contains(path));
                log.info("RouteValidator: path={}, isOpenEndpoint={}, isSecured={}", path, isOpen, !isOpen);
                return !isOpen;
            };
}