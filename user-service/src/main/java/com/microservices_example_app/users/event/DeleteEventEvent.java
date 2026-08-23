package com.microservices_example_app.users.event;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
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
    @NotEmpty(message = "Events must not be empty")
    private List<String> events;
    @NotBlank(message = "Source service must not be blank")
    private String sourceService;
    private List<Integer> userIds;

}