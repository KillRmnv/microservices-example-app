package com.microservices_example_app.booking.controller;

import com.microservices_example_app.booking.dto.TownCreateRequestDto;
import com.microservices_example_app.booking.dto.TownResponseDto;
import com.microservices_example_app.booking.service.TownService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/booking/towns")
@RequiredArgsConstructor
public class TownController {

    private final TownService townService;

    @PostMapping
    public TownResponseDto create(@RequestBody TownCreateRequestDto requestDto) {
        return townService.create(requestDto);
    }

    @GetMapping("/{id}")
    public TownResponseDto getById(@PathVariable Integer id) {
        return townService.getById(id);
    }

    @GetMapping
    public List<TownResponseDto> getAll() {
        return townService.getAll();
    }

    @DeleteMapping("/{id}")
    public void deleteById(@PathVariable Integer id) {
        townService.delete(id);
    }
}