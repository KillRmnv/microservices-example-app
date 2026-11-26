package com.microservices_example_app.booking.config;

import io.swagger.v3.oas.annotations.OpenAPIDefinition;
import io.swagger.v3.oas.annotations.info.Info;
import io.swagger.v3.oas.models.media.ArraySchema;
import io.swagger.v3.oas.models.media.Content;
import io.swagger.v3.oas.models.media.IntegerSchema;
import io.swagger.v3.oas.models.media.MediaType;
import io.swagger.v3.oas.models.media.ObjectSchema;
import io.swagger.v3.oas.models.media.StringSchema;
import io.swagger.v3.oas.models.responses.ApiResponse;
import org.springdoc.core.customizers.OpenApiCustomizer;
import org.springdoc.core.models.GroupedOpenApi;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@OpenAPIDefinition(
        info = @Info(
                title = "Booking Service API",
                version = "v1",
                description = "Event, venue, seat and ticket booking endpoints"
        )
)
@Configuration
public class OpenApiConfiguration {

    @Bean
    public GroupedOpenApi publicApi() {
        return GroupedOpenApi.builder()
                .group("booking-service")
                .pathsToMatch("/booking/**")
                .pathsToExclude("/actuator/**", "/fallback/**")
                .build();
    }

    /**
     * Documents the error responses produced by the global
     * {@code @RestControllerAdvice} on every operation, so per-endpoint
     * {@code @ApiResponse} repetition is unneeded.
     */
    @Bean
    public OpenApiCustomizer problemResponses() {
        return openApi -> {
            if (openApi.getPaths() == null) {
                return;
            }
            openApi.getPaths().values().forEach(pathItem ->
                    pathItem.readOperations().forEach(operation -> {
                        operation.getResponses().addApiResponse("400",
                                problem("Bad Request", "validation_error", 400,
                                        "Validation failed", true));
                        operation.getResponses().addApiResponse("404",
                                problem("Not Found", "not_found", 404,
                                        "Event not found", false));
                        operation.getResponses().addApiResponse("500",
                                problem("Internal Server Error", "internal_error", 500,
                                        "Internal server error", false));
                    }));
        };
    }

    private static ApiResponse problem(String title, String code, int status,
                                       String detail, boolean withErrors) {
        ObjectSchema schema = new ObjectSchema();
        schema.addProperty("type", new StringSchema()
                .description("Problem type URI")
                .example("https://dosug.example/problems/" + code));
        schema.addProperty("title", new StringSchema().example(title));
        schema.addProperty("status", new IntegerSchema().example(status));
        schema.addProperty("detail", new StringSchema().example(detail));
        schema.addProperty("instance", new StringSchema()
                .description("Request path").example("/booking/events"));
        schema.addProperty("code", new StringSchema()
                .description("Stable machine-readable code").example(code));
        schema.addProperty("traceId", new StringSchema()
                .description("Echoes the X-Request-ID header").example("req-123"));
        if (withErrors) {
            ObjectSchema fieldError = new ObjectSchema();
            fieldError.addProperty("field", new StringSchema().example("title"));
            fieldError.addProperty("code", new StringSchema().example("NotBlank"));
            fieldError.addProperty("message",
                    new StringSchema().example("Title must not be blank"));
            schema.addProperty("errors", new ArraySchema().items(fieldError));
        }
        Content content = new Content().addMediaType("application/problem+json",
                new MediaType().schema(schema));
        return new ApiResponse().description(title).content(content);
    }
}
