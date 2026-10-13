namespace SaigonRide.App.Models.Entities;

public class StationUtilisationLog
{
    public int Id { get; set; }
    public int StationId { get; set; }
    public Station Station { get; set; } = null!;
    
    public DateTime HourSlot { get; set; }      // truncated to the hour, UTC
    public int BikesAvailable { get; set; }     // snapshot at time of logging
    public int Capacity { get; set; }           // denormalized intentionally — capacity can change
    public int RentalsStarted { get; set; }     // departures during this hour
    public int RentalsEnded { get; set; }       // arrivals during this hour
}    
