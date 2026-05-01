package com.microservices_example_app.booking.repository;

import com.microservices_example_app.booking.model.Seat;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface SeatRepository extends JpaRepository<Seat, Integer>, JpaSpecificationExecutor<Seat> {
    List<Seat> findByVenueId(Integer venueId);

    List<Seat> findByVenueIdAndSectorIgnoreCase(Integer venueId, String sector);

    Optional<Seat> findByVenueIdAndSectorIgnoreCaseAndRowIgnoreCaseAndNumber(
            Integer venueId,
            String sector,
            String row,
            String number
    );

    boolean existsByVenueIdAndSectorIgnoreCaseAndRowIgnoreCaseAndNumber(
            Integer venueId,
            String sector,
            String row,
            String number
    );
}