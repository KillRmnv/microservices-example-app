package com.microservices_example_app.users.event;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.util.List;
@NoArgsConstructor
@Getter
@Setter
public class MassDeleteEventMailingEvent extends MassMailingUserEvent{
    private List<String> events;

    public MassDeleteEventMailingEvent(List<String> events,List<UserNotificationDto> userIds,String sourceService){
        super(userIds,sourceService);
        this.events=events;

    }
}
