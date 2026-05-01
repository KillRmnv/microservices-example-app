package com.microservices_example_app.users.event;

import jakarta.validation.constraints.NotBlank;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.util.List;

@NoArgsConstructor
@Getter
@Setter
public class MassUpdateEventMailingEvent extends MassMailingUserEvent {

    private List<String> events;
    @NotBlank(message = "Changes description must not be blank")
    private String changesDescription;

    public MassUpdateEventMailingEvent(List<String> events,String changesDescription,List<UserNotificationDto> userIds,String sourceService){
        super(userIds,sourceService);
        this.events=events;
        this.changesDescription=changesDescription;
    }
}
