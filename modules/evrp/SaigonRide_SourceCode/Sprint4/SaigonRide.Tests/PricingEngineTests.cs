using SaigonRide.App.Services;
using FluentAssertions;

namespace SaigonRide.Tests;

public class PricingEngineTests
{
    private static readonly DateTime Base = new(2025, 1, 1, 10, 0, 0, DateTimeKind.Utc);

    [Fact]
    public void HourlyFare_LessThanOneHour_BillsMinimumOneHour()
    {
        var fare = PricingEngine.CalculateHourlyFare(20000m, Base, Base.AddMinutes(30));
        fare.Should().Be(20000m);
    }

    [Fact]
    public void HourlyFare_TwoAndHalfHours_BillsThreeHours()
    {
        var fare = PricingEngine.CalculateHourlyFare(20000m, Base, Base.AddHours(2.5));
        fare.Should().Be(60000m);
    }

    [Fact]
    public void DailyFare_FiveHours_BillsMinimumOneDay()
    {
        var fare = PricingEngine.CalculateDailyFare(150000m, Base, Base.AddHours(5));
        fare.Should().Be(150000m);
    }

    [Fact]
    public void Deposit_GradeA_Is20Percent()
    {
        var deposit = PricingEngine.CalculateDepositAmount(10_000_000m, grade: 2);
        deposit.Should().Be(2_000_000m);
    }

    [Fact]
    public void Deposit_GradeC_Is10Percent()
    {
        var deposit = PricingEngine.CalculateDepositAmount(2_000_000m, grade: 0);
        deposit.Should().Be(200_000m);
    }

    [Fact]
    public void Fare_ZeroMinutes_BillsMinimumOneHour()
    {
        var fare = PricingEngine.CalculateHourlyFare(20000m, Base, Base);
        fare.Should().Be(20000m);
    }

    [Fact]
    public void Fare_ExactlyOneHour_BillsOneHour()
    {
        var fare = PricingEngine.CalculateHourlyFare(20000m, Base, Base.AddHours(1));
        fare.Should().Be(20000m);
    }

    [Fact]
    public void Fare_OneHourOneMinute_BillsTwoHours()
    {
        var fare = PricingEngine.CalculateHourlyFare(20000m, Base, Base.AddHours(1).AddMinutes(1));
        fare.Should().Be(40000m);
    }

    [Fact]
    public void Discount_StationBelow20Percent_Applies15Percent()
    {
        // Station with 20 capacity, 3 vehicles = 15% utilization = qualifies
        var fare        = 100000m;
        var discounted  = PricingEngine.ApplyLowInventoryDiscount(fare, currentCount: 3, capacity: 20);
        discounted.Should().Be(85000m);
    }

    [Fact]
    public void Discount_StationAbove20Percent_NoDiscount()
    {
        // Station with 20 capacity, 5 vehicles = 25% utilization = no discount
        var fare        = 100000m;
        var discounted  = PricingEngine.ApplyLowInventoryDiscount(fare, currentCount: 5, capacity: 20);
        discounted.Should().Be(100000m);
    }

    [Fact]
    public void Discount_StationExactly20Percent_NoDiscount()
    {
        // Boundary: exactly 20% = no discount
        var fare        = 100000m;
        var discounted  = PricingEngine.ApplyLowInventoryDiscount(fare, currentCount: 4, capacity: 20);
        discounted.Should().Be(100000m);
    }
}