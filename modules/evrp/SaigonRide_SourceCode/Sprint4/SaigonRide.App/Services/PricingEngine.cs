namespace SaigonRide.App.Services;

public static class PricingEngine
{
    public static decimal CalculateHourlyFare(decimal hourlyRate, DateTime start, DateTime end)
    {
        var hours = Math.Max(1, (int)Math.Ceiling((end - start).TotalHours));
        return hours * hourlyRate;
    }

    public static decimal CalculateDailyFare(decimal dailyRate, DateTime start, DateTime end)
    {
        var days = Math.Max(1, (int)Math.Ceiling((end - start).TotalDays));
        return days * dailyRate;
    }

    public static decimal CalculateDepositAmount(decimal marketValue, int grade)
    {
        var rate = grade switch { 2 => 0.20m, 1 => 0.15m, _ => 0.10m };
        return Math.Round(marketValue * rate, 0);
    }

    public static decimal ApplyLowInventoryDiscount(decimal fare, int currentCount, int capacity)
    {
        var utilization = (decimal)currentCount / capacity;
        return utilization < 0.20m ? fare * 0.85m : fare;
    }
}