package com.microservices_example_app.booking.repository;

import com.microservices_example_app.booking.model.Seat;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface SeatRepository extends JpaRepository<Seat, Long>, JpaSpecificationExecutor<Seat> {
    List<Seat> findByVenueId(Long venueId);

    List<Seat> findByVenueIdAndSectorIgnoreCase(Long venueId, String sector);

    Optional<Seat> findByVenueIdAndSectorIgnoreCaseAndRowIgnoreCaseAndNumber(
            Long venueId,
            String sector,
            String row,
            String number
    );

    boolean existsByVenueIdAndSectorIgnoreCaseAndRowIgnoreCaseAndNumber(
            Long venueId,
            String sector,
            String row,
            String number
    );
}