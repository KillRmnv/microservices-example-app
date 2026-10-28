package com.microservices_example_app.gateway.configuration;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.Operation;
import io.swagger.v3.oas.models.PathItem;
import io.swagger.v3.oas.models.Paths;
import io.swagger.v3.oas.models.responses.ApiResponse;
import io.swagger.v3.oas.models.responses.ApiResponses;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class OpenApiProblemResponsesTest {

    @Test
    void addsUnauthorizedProblemResponse() {
        OpenAPI openAPI = new OpenAPI();
        Operation operation = new Operation();
        operation.setResponses(new ApiResponses()
                .addApiResponse("200", new ApiResponse().description("OK")));
        openAPI.setPaths(new Paths()
                .addPathItem("/fallback/users", new PathItem().get(operation)));

        new OpenApiConfiguration().problemResponses().customise(openAPI);

        ApiResponses responses = openAPI.getPaths()
                .get("/fallback/users").getGet().getResponses();
        assertThat(responses).containsKeys("200", "401");
        assertThat(responses.get("401").getContent())
                .containsKey("application/problem+json");
        assertThat(responses.get("401").getContent()
                .get("application/problem+json").getSchema().getProperties())
                .containsKeys("type", "title", "status", "detail", "instance",
                        "code", "traceId");
    }
}
