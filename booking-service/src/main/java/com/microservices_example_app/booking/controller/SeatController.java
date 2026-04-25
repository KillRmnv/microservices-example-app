package com.microservices_example_app.booking.controller;

import com.microservices_example_app.booking.dto.*;
import com.microservices_example_app.booking.service.SeatService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/booking/seats")
@RequiredArgsConstructor
public class SeatController {

    private final SeatService seatService;

    @PostMapping
    public SeatResponseDto create(@RequestBody SeatCreateRequestDto requestDto) {
        return seatService.create(requestDto);
    }

    @GetMapping("/{id}")
    public SeatResponseDto getById(@PathVariable Integer id) {
        return seatService.getById(id);
    }

    @GetMapping("/search")
    public List<SeatResponseDto> searchByFilter(@ModelAttribute SeatSearchRequestDto filter,
                                                @RequestParam(defaultValue = "1") int page,
                                                @RequestParam(defaultValue = "10") int size) {
        return seatService.searchByFilter(filter, page, size);
    }

    @PutMapping("/{id}")
    public SeatResponseDto updateById(@PathVariable Integer id,
                                      @RequestBody SeatUpdateRequestDto requestDto) {
        requestDto.setId(id);
        return seatService.updateSeatById(requestDto);
    }

    @DeleteMapping("/{id}")
    public void deleteById(@PathVariable Integer id) {
        seatService.deleteById(id);
    }

    @DeleteMapping("/search")
    public long deleteByFilter(@RequestBody SeatDeleteRequestDto requestDto) {
        return seatService.deleteByFilter(requestDto);
    }
}