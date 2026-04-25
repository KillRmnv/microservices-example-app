package com.microservices_example_app.booking.dto;

import com.microservices_example_app.booking.model.EventAdmissionMode;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;
@AllArgsConstructor
@Getter
@Setter
public class EventUpdateRequestDto {
    private Integer id;
    private String title;
    private LocalDateTime startsAt;
    private LocalDateTime endsAt;
    private Integer venueId;
    private String venuePlace;
    private EventAdmissionMode admissionMode;

}
