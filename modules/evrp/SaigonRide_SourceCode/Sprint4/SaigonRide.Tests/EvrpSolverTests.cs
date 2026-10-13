using System;
using System.Collections.Generic;
using System.Linq;
using Xunit;
using FluentAssertions;
using SaigonRide.App.Services;
using SaigonRide.App.Models.Entities;

namespace SaigonRide.Tests
{
    public class EvrpSolverTests
    {
        private readonly EvrpSolverService _solver = new EvrpSolverService();

        [Fact]
        public void CalculateDistance_BenThanhToNguyenHue_ReturnsCorrectDistance()
        {
            // Ben Thanh: 10.7721, 106.6980
            // Nguyen Hue: 10.7743, 106.7030
            double dist = _solver.CalculateDistance(10.7721, 106.6980, 10.7743, 106.7030);
            
            // Should be roughly ~0.59 km
            dist.Should().BeInRange(0.5, 0.7);
        }

        [Fact]
        public void Solve_SingleDonorAndSingleRecipient_GeneratesFeasibleRoute()
        {
            // Set up a simple 3 station system:
            // Depot (Ben Thanh), Donor (Nguyen Hue), Recipient (Bui Vien)
            var stations = new List<Station>
            {
                new Station { Id = 1, Name = "Ben Thanh (Depot)", Latitude = 10.7721, Longitude = 106.6980, Capacity = 20 },
                new Station { Id = 2, Name = "Nguyen Hue (Donor)", Latitude = 10.7743, Longitude = 106.7030, Capacity = 20 },
                new Station { Id = 3, Name = "Bui Vien (Recipient)", Latitude = 10.7676, Longitude = 106.6920, Capacity = 20 }
            };

            // Map current available bikes:
            // Target is Capacity/2 = 10.
            // Donor (Nguyen Hue) has 15 available bikes (5 surplus)
            // Recipient (Bui Vien) has 5 available bikes (5 deficit)
            var availableMap = new Dictionary<int, int>
            {
                { 1, 10 }, // Balanced depot
                { 2, 15 }, // 5 surplus
                { 3, 5 }   // 5 deficit
            };

            var solution = _solver.Solve(stations, availableMap, depotId: 1);

            // Assertions
            solution.Should().NotBeNull();
            solution.BikesMoved.Should().Be(5);
            solution.IsFeasible.Should().BeTrue();
            
            // Sequence starts and ends at Depot (Station 1)
            solution.Steps.First().StationId.Should().Be(1);
            solution.Steps.First().Action.Should().Be("Start");
            solution.Steps.Last().StationId.Should().Be(1);
            solution.Steps.Last().Action.Should().Be("End");

            // Check that capacity constraint was never violated
            foreach (var step in solution.Steps)
            {
                step.VehicleLoadAfter.Should().BeInRange(0, EvrpSolverService.VehicleCapacity);
                step.VehicleBatteryAfter.Should().BeInRange(0.0, 100.0);
            }
        }

        [Fact]
        public void Solve_VehiclesCapacity_LimitsCargoLoads()
        {
            var stations = new List<Station>
            {
                new Station { Id = 1, Name = "Ben Thanh", Latitude = 10.7721, Longitude = 106.6980, Capacity = 10 },
                new Station { Id = 2, Name = "Mega Donor", Latitude = 10.7743, Longitude = 106.7030, Capacity = 40 }, // Target=20
                new Station { Id = 3, Name = "Mega Recipient", Latitude = 10.7676, Longitude = 106.6920, Capacity = 40 } // Target=20
            };

            var availableMap = new Dictionary<int, int>
            {
                { 1, 5 },
                { 2, 35 }, // 15 surplus
                { 3, 5 }   // 15 deficit
            };

            var solution = _solver.Solve(stations, availableMap, depotId: 1);

            // Even though 15 bikes are needed, the vehicle capacity is 10, so max load at a time is 10.
            foreach (var step in solution.Steps)
            {
                step.VehicleLoadAfter.Should().BeInRange(0, EvrpSolverService.VehicleCapacity);
            }
            solution.BikesMoved.Should().BeLessThanOrEqualTo(EvrpSolverService.VehicleCapacity);
        }

        [Fact]
        public void Solve_LongDistance_TriggersBatteryRecharge()
        {
            // Far station (outside standard District 1 bounds to trigger recharge)
            var stations = new List<Station>
            {
                new Station { Id = 1, Name = "Ben Thanh (Depot)", Latitude = 10.7721, Longitude = 106.6980, Capacity = 10 },
                new Station { Id = 2, Name = "Far Station (Donor)", Latitude = 11.2000, Longitude = 107.2000, Capacity = 20 }, // very far, > 50km
                new Station { Id = 3, Name = "Ben Thanh (Recipient)", Latitude = 10.7721, Longitude = 106.6980, Capacity = 20 }
            };

            var availableMap = new Dictionary<int, int>
            {
                { 1, 5 },
                { 2, 15 },
                { 3, 5 }
            };

            var solution = _solver.Solve(stations, availableMap, depotId: 1);

            // Since it is very far, the battery depletion must trigger at least one Recharge action
            solution.Steps.Any(s => s.Action == "Recharge").Should().BeTrue();
            solution.Steps.Last().VehicleBatteryAfter.Should().BeInRange(0.0, 100.0);
        }
    }
}
