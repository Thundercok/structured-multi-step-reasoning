using Microsoft.AspNetCore.SignalR;
using Microsoft.AspNetCore.Authorization;

namespace SaigonRide.App.Hubs;
[Authorize(Roles = "Admin")]   // ← add this

public class AdminHub : Hub
{
    public static async Task NotifyStationUpdate(IHubContext<AdminHub> hub, object stationData)
    {
        await hub.Clients.All.SendAsync("StationUpdated", stationData);
    }

    public static async Task NotifyNewActiveRental(IHubContext<AdminHub> hub, object rentalData)
    {
        await hub.Clients.All.SendAsync("NewActiveRental", rentalData);
    }
}
