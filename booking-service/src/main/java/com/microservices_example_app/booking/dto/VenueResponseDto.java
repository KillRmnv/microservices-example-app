package com.microservices_example_app.booking.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.io.Serializable;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class VenueResponseDto implements Serializable {
    private static final long serialVersionUID = 1L;
    private Integer id;
    private Integer townId;
    private String townName;
    private String place;
    private Integer capacity;
}