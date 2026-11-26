package com.microservices_example_app.users.configuration;


import com.microservices_example_app.users.filters.JwtAuthenticationFilter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpStatus;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import tools.jackson.databind.ObjectMapper;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

@Configuration
@EnableMethodSecurity(prePostEnabled = true)
public class SecurityConfiguration {

    private final JwtAuthenticationFilter jwtFilter;

    private final ObjectMapper objectMapper;

    public SecurityConfiguration(JwtAuthenticationFilter jwtFilter , ObjectMapper objectMapper) {
        this.jwtFilter = jwtFilter;
        this.objectMapper = objectMapper;
    }

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) {
        return http
                .csrf(csrf -> csrf.disable())
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/users/auth/**",
                                "/actuator/health/**",
                                "/actuator/prometheus",
                                "/v3/api-docs/**",
                                "/swagger-ui/**",
                                "/swagger-ui.html"
                                ).permitAll()
                        .requestMatchers("/admin/**").hasRole("ADMIN")
                        .requestMatchers("/manager/**").hasRole("EVENT_MANAGER")
                        .anyRequest().authenticated())
                .exceptionHandling(ex -> ex
                        .authenticationEntryPoint((request, response, authException) -> {
                            SecurityContextHolder.clearContext();
                            writeProblem(request, response, HttpStatus.UNAUTHORIZED,
                                    "unauthorized", authException.getMessage());
                        })
                        .accessDeniedHandler((request, response, accessDeniedException) -> {
                            SecurityContextHolder.clearContext();
                            writeProblem(request, response, HttpStatus.FORBIDDEN,
                                    "forbidden", "Insufficient permissions");
                        }))
                .addFilterBefore(jwtFilter, UsernamePasswordAuthenticationFilter.class)


                .build();
    }

    /**
     * RFC 9457 error body, flat like the {@code @RestControllerAdvice} responses
     * (Spring Security runs before MVC, so the advice cannot handle these).
     */
    private void writeProblem(jakarta.servlet.http.HttpServletRequest request,
                              jakarta.servlet.http.HttpServletResponse response,
                              HttpStatus status, String code, String detail) throws java.io.IOException {
        String header = request.getHeader("X-Request-ID");
        String traceId = (header != null && !header.isBlank())
                ? header : UUID.randomUUID().toString();
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("type", "https://dosug.example/problems/" + code);
        body.put("title", status.getReasonPhrase());
        body.put("status", status.value());
        body.put("detail", detail);
        body.put("instance", request.getRequestURI());
        body.put("code", code);
        body.put("traceId", traceId);
        response.setStatus(status.value());
        response.setContentType("application/problem+json");
        response.setHeader("X-Request-ID", traceId);
        objectMapper.writeValue(response.getWriter(), body);
    }
}
