package com.microservices_example_app.booking;

import com.microservices_example_app.booking.controller.EventController;
import com.microservices_example_app.booking.dto.AvailabilityStatus;
import com.microservices_example_app.booking.dto.EventAvailabilityResponseDto;
import com.microservices_example_app.booking.dto.ZoneAvailabilityDto;
import com.microservices_example_app.booking.exceptions.GlobalControllerAdvice;
import com.microservices_example_app.booking.exceptions.NotFoundException;
import com.microservices_example_app.booking.model.Zone;
import com.microservices_example_app.booking.service.EventService;
import com.microservices_example_app.booking.utils.JwtRequestUserExtractor;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.math.BigDecimal;
import java.util.List;

import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.notNullValue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class EventAvailabilityControllerTest {

    private EventService eventService;
    private MockMvc mockMvc;

    @BeforeEach
    void setup() {
        eventService = mock(EventService.class);
        mockMvc = MockMvcBuilders
                .standaloneSetup(new EventController(eventService, mock(JwtRequestUserExtractor.class)))
                .setControllerAdvice(new GlobalControllerAdvice())
                .build();
    }

    @Test
    void availabilityReturnsPartyAwareSnapshot() throws Exception {
        when(eventService.availability(100L, 2)).thenReturn(EventAvailabilityResponseDto.builder()
                .eventId(100L)
                .status(AvailabilityStatus.AVAILABLE)
                .capacity(150)
                .zones(List.of(
                        ZoneAvailabilityDto.builder()
                                .zone(Zone.VIP)
                                .seatsLeft(20L)
                                .minPrice(new BigDecimal("100.00"))
                                .build(),
                        ZoneAvailabilityDto.builder()
                                .zone(Zone.BASIC)
                                .seatsLeft(9L)
                                .minPrice(new BigDecimal("30.00"))
                                .build()))
                .build());

        mockMvc.perform(get("/booking/events/100/availability").param("party", "2"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.eventId").value(100))
                .andExpect(jsonPath("$.status").value("available"))
                .andExpect(jsonPath("$.capacity").value(150))
                .andExpect(jsonPath("$.zones", hasSize(2)))
                .andExpect(jsonPath("$.zones[0].zone").value("VIP"))
                .andExpect(jsonPath("$.zones[0].seatsLeft").value(20))
                .andExpect(jsonPath("$.zones[0].minPrice").value(100.0))
                .andExpect(jsonPath("$.zones[1].zone").value("BASIC"));

        verify(eventService).availability(100L, 2);
    }

    @Test
    void availabilityDefaultsPartyToZero() throws Exception {
        when(eventService.availability(100L, 0)).thenReturn(EventAvailabilityResponseDto.builder()
                .eventId(100L)
                .status(AvailabilityStatus.SOLD_OUT)
                .capacity(150)
                .zones(List.of())
                .build());

        mockMvc.perform(get("/booking/events/100/availability"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("sold_out"))
                .andExpect(jsonPath("$.zones", hasSize(0)));

        verify(eventService).availability(100L, 0);
    }

    @Test
    void availabilityReturnsProblemDetailWhenEventIsMissing() throws Exception {
        when(eventService.availability(404L, 0)).thenThrow(new NotFoundException("Event not found"));

        mockMvc.perform(get("/booking/events/404/availability"))
                .andExpect(status().isNotFound())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.code").value("not_found"))
                .andExpect(jsonPath("$.status").value(404))
                .andExpect(jsonPath("$.detail").value("Event not found"))
                .andExpect(jsonPath("$.traceId", notNullValue()));
    }
}
