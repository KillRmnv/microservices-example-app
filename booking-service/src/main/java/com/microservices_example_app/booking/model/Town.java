package com.microservices_example_app.booking.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import lombok.experimental.SuperBuilder;

@Entity
@Table(name = "towns")
@Getter
@Setter
@SuperBuilder
@NoArgsConstructor
public class Town extends BaseEntity {

    @Column(nullable = false, unique = true)
    private String name;
}