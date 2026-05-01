package com.microservices_example_app.booking.event;

import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.util.List;

@AllArgsConstructor
@NoArgsConstructor
@Getter
@Setter
public class UpdateEventEvent {
    @NotBlank(message = "Event must not be blank")
    private List<String> events;
    @NotBlank(message = "Source service must not be blank")
    private String sourceService;
    @NotBlank(message = "Changes description must not be blank")
    private String changesDescription;
    private List<Integer> userIds;
}
