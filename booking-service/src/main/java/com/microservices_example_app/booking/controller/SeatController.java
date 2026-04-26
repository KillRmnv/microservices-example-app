package com.microservices_example_app.booking.controller;

import com.microservices_example_app.booking.dto.*;
import com.microservices_example_app.booking.service.SeatService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/booking/seats")
@RequiredArgsConstructor
@Slf4j
public class SeatController {

    private final SeatService seatService;

    @PostMapping
    public SeatResponseDto create(@Valid @RequestBody SeatCreateRequestDto requestDto) {
        log.info("Creating new seat in venue id: {}", requestDto.getVenueId());
        return seatService.create(requestDto);
    }

    @GetMapping("/{id}")
    public SeatResponseDto getById(@PathVariable Integer id) {
        log.info("Fetching seat with id: {}", id);
        return seatService.getById(id);
    }

    @GetMapping("/search")
    public List<SeatResponseDto> searchByFilter(@Valid @ModelAttribute SeatSearchRequestDto filter,
                                                @RequestParam(defaultValue = "1") int page,
                                                @RequestParam(defaultValue = "10") int size) {
        return seatService.searchByFilter(filter, page, size);
    }

    @PutMapping("/{id}")
    public SeatResponseDto updateById(@PathVariable Integer id,
                                      @Valid @RequestBody SeatUpdateRequestDto requestDto) {
        requestDto.setId(id);
        return seatService.updateSeatById(requestDto);
    }

    @DeleteMapping("/{id}")
    public void deleteById(@PathVariable Integer id) {
        log.info("Deleting seat with id: {}", id);
        seatService.deleteById(id);
    }

    @DeleteMapping("/search")
    public long deleteByFilter(@Valid @RequestBody SeatDeleteRequestDto requestDto) {
        return seatService.deleteByFilter(requestDto);
    }
}