package com.microservices_example_app.gateway.configuration;

import io.swagger.v3.oas.annotations.OpenAPIDefinition;
import io.swagger.v3.oas.annotations.info.Info;
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
                title = "Gateway API",
                version = "v1",
                description = "API gateway entry point. Proxied downstream routes (/users/**, /booking/**, /assistant/**) are documented by their owning services; only the gateway's own endpoints are listed here."
        )
)
@Configuration
public class OpenApiConfiguration {

    @Bean
    public GroupedOpenApi publicApi() {
        return GroupedOpenApi.builder()
                .group("gateway")
                .pathsToExclude("/actuator/**", "/fallback/**", "/users/**", "/booking/**", "/assistant/**")
                .build();
    }

    /**
     * Documents the 401 produced by the JWT global filter on every operation.
     * (503 fallback responses live on the excluded {@code /fallback/**} paths.)
     */
    @Bean
    public OpenApiCustomizer problemResponses() {
        return openApi -> {
            if (openApi.getPaths() == null) {
                return;
            }
            openApi.getPaths().values().forEach(pathItem ->
                    pathItem.readOperations().forEach(operation ->
                            operation.getResponses().addApiResponse("401",
                                    problem("Unauthorized", "unauthorized", 401,
                                            "Authorization header is missing or invalid"))));
        };
    }

    private static ApiResponse problem(String title, String code, int status,
                                       String detail) {
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
        Content content = new Content().addMediaType("application/problem+json",
                new MediaType().schema(schema));
        return new ApiResponse().description(title).content(content);
    }
}
