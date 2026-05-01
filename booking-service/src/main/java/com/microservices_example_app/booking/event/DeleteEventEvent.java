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
public class DeleteEventEvent {
    @NotBlank(message = "Event must not be blank")
    private List<String> events;
    @NotBlank(message = "Source service must not be blank")
    private String sourceService;
    private List<Integer> userIds;

}
