package com.microservices_example_app.booking;

import com.microservices_example_app.booking.exceptions.GlobalControllerAdvice;
import com.microservices_example_app.booking.exceptions.NotFoundException;
import jakarta.validation.ConstraintViolationException;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Collections;

import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.notNullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class ProblemDetailExceptionHandlingTest {

    private MockMvc mockMvc;

    @Getter
    @Setter
    @NoArgsConstructor
    @AllArgsConstructor
    static class StubRequest {
        @NotBlank(message = "Name must not be blank")
        private String name;
    }

    @RestController
    @RequestMapping("/stub")
    static class StubController {

        @GetMapping("/not-found")
        public String notFound() {
            throw new NotFoundException("Ticket not found");
        }

        @GetMapping("/illegal-argument")
        public String illegalArgument() {
            throw new IllegalArgumentException("Bad argument");
        }

        @GetMapping("/constraint-violation")
        public String constraintViolation() {
            throw new ConstraintViolationException("Validation failed", Collections.emptySet());
        }

        @GetMapping("/boom")
        public String boom() {
            throw new RuntimeException("boom");
        }

        @PostMapping("/validated")
        public String validated(@Valid @RequestBody StubRequest request) {
            return "ok:" + request.getName();
        }
    }

    @BeforeEach
    void setup() {
        mockMvc = MockMvcBuilders.standaloneSetup(new StubController())
                .setControllerAdvice(new GlobalControllerAdvice())
                .build();
    }

    @Test
    void notFoundReturnsProblemDetail() throws Exception {
        mockMvc.perform(get("/stub/not-found"))
                .andExpect(status().isNotFound())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.type").value("https://dosug.example/problems/not_found"))
                .andExpect(jsonPath("$.status").value(404))
                .andExpect(jsonPath("$.detail").value("Ticket not found"))
                .andExpect(jsonPath("$.instance").value("/stub/not-found"))
                .andExpect(jsonPath("$.code").value("not_found"))
                .andExpect(jsonPath("$.traceId", notNullValue()))
                .andExpect(jsonPath("$.title", notNullValue()));
    }

    @Test
    void illegalArgumentReturnsProblemDetail() throws Exception {
        mockMvc.perform(get("/stub/illegal-argument"))
                .andExpect(status().isBadRequest())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.type").value("https://dosug.example/problems/illegal_argument"))
                .andExpect(jsonPath("$.code").value("illegal_argument"))
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.detail").value("Bad argument"))
                .andExpect(jsonPath("$.traceId", notNullValue()));
    }

    @Test
    void genericExceptionHidesInternals() throws Exception {
        mockMvc.perform(get("/stub/boom"))
                .andExpect(status().isInternalServerError())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.code").value("internal_error"))
                .andExpect(jsonPath("$.type").value("https://dosug.example/problems/internal_error"))
                .andExpect(jsonPath("$.detail").value("Internal server error"));
    }

    @Test
    void validationFailureReturnsErrorsArray() throws Exception {
        mockMvc.perform(post("/stub/validated")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"name\":\"\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.code").value("validation_error"))
                .andExpect(jsonPath("$.type").value("https://dosug.example/problems/validation_error"))
                .andExpect(jsonPath("$.errors", hasSize(1)))
                .andExpect(jsonPath("$.errors[0].field").value("name"))
                .andExpect(jsonPath("$.errors[0].message").value("Name must not be blank"))
                .andExpect(jsonPath("$.errors[0].code", notNullValue()));
    }

    @Test
    void malformedBodyReturnsProblemDetail() throws Exception {
        mockMvc.perform(post("/stub/validated")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{not-json"))
                .andExpect(status().isBadRequest())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.code").value("http_message_not_readable"))
                .andExpect(jsonPath("$.type")
                        .value("https://dosug.example/problems/http_message_not_readable"));
    }

    @Test
    void constraintViolationReturnsProblemDetail() throws Exception {
        mockMvc.perform(get("/stub/constraint-violation"))
                .andExpect(status().isBadRequest())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.code").value("validation_error"));
    }

    @Test
    void traceIdEchoesRequestIdHeader() throws Exception {
        mockMvc.perform(get("/stub/boom").header("X-Request-ID", "req-456"))
                .andExpect(status().isInternalServerError())
                .andExpect(jsonPath("$.traceId").value("req-456"));
    }
}
