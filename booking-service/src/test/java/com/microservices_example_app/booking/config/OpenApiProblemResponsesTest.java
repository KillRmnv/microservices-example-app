package com.microservices_example_app.booking.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.Operation;
import io.swagger.v3.oas.models.PathItem;
import io.swagger.v3.oas.models.Paths;
import io.swagger.v3.oas.models.responses.ApiResponse;
import io.swagger.v3.oas.models.responses.ApiResponses;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class OpenApiProblemResponsesTest {

    @Test
    void addsProblemResponsesToEveryOperation() {
        OpenAPI openAPI = new OpenAPI();
        Operation operation = new Operation();
        operation.setResponses(new ApiResponses()
                .addApiResponse("200", new ApiResponse().description("OK")));
        openAPI.setPaths(new Paths()
                .addPathItem("/booking/events", new PathItem().get(operation)));

        new OpenApiConfiguration().problemResponses().customise(openAPI);

        ApiResponses responses = openAPI.getPaths()
                .get("/booking/events").getGet().getResponses();
        for (String code : List.of("200", "400", "404", "500")) {
            assertThat(responses).containsKey(code);
        }
        assertThat(responses.get("400").getContent()
                .get("application/problem+json").getSchema().getProperties())
                .containsKeys("code", "traceId", "errors");
    }
}
