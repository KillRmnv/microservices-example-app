package com.microservices_example_app.booking.dto;

import com.microservices_example_app.booking.model.EventAdmissionMode;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.LocalDateTime;
@AllArgsConstructor
@NoArgsConstructor
@Getter
@Setter
@Schema(description = "Request to update an existing event")
public class EventUpdateRequestDto {
    private Integer id;
    private String title;
    private LocalDateTime startsAt;
    private LocalDateTime endsAt;
    private Integer venueId;
    private String venuePlace;
    private EventAdmissionMode admissionMode;

}
