# TGF3162 Controller

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Python and FastAPI are user requirements. A lightweight, framework-free HTML/CSS/JavaScript frontend is an implementation choice: no Node build or internet connection is required on the lab computer.

## Users

A laboratory user configuring two independent sine outputs, by browser or Python script.

## Product Purpose

Control an Aim-TTi TGF3162 over Ethernet through a switch. Set frequency, amplitude, phase, internal sine AM/FM, and each output independently.

## Operating Context

Windows and Ubuntu. Development currently has no connected instrument. Provide an explicit demo mode and configurable IP with an identity-based connection test.

## Capabilities and Constraints

50 ohm load; Vpp, Vrms and dBm entry; zero DC offset in this version. No synchronous start. AM and FM are mutually exclusive. Instrument commands accept Vpp, so other units are converted. Hardware settings are not individually queryable in the published manual: distinguish acknowledged commands from measured or read-back state. No automatic output enable on connect.

## Brand Commitments

English UI, code and documentation; Chinese conversation. Simple, clear, ergonomic controls. The user requested Taste and Impeccable. Taste v2 excludes dashboards; use Impeccable Operate guidance for the control surface.

## Evidence on Hand

Aim-TTi TGF3000 instruction manual Issue 5 download, specifications and command list. No physical instrument test or measurement evidence exists yet.

## Product Principles

Keep channels independent. Make units explicit. Validate before writing. Never present a simulation or cached command as hardware measurement. Preserve unsent edits during connection checks.
