package com.microservices_example_app.gateway.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.config.ResourceHandlerRegistry;
import org.springframework.web.reactive.config.WebFluxConfigurer;

@Configuration
public class WebConfig implements WebFluxConfigurer {

    private final String frontendPath;

    public WebConfig(@Value("${app.frontend-path}") String frontendPath) {
        this.frontendPath = frontendPath;
    }

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        String normalizedPath = frontendPath.endsWith("/") ? frontendPath : frontendPath + "/";
        String resourceLocation = normalizedPath.startsWith("file:")
                ? normalizedPath
                : "file:" + normalizedPath;

        registry.addResourceHandler("/**")
                .addResourceLocations(resourceLocation);
    }
}