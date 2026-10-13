using Microsoft.AspNetCore.SignalR;

namespace SaigonRide.App.Hubs;

public class RentalHub : Hub
{
    private static string RentalGroupName(int rentalId) => $"rental_{rentalId}";
    
    public async Task JoinRentalGroup(int rentalId)
    {
        var userId = Context.UserIdentifier;

       
        var personalGroup = $"rental_{rentalId}_{userId}";
        await Groups.AddToGroupAsync(Context.ConnectionId, personalGroup);
    }

    public async Task LeaveRentalGroup(int rentalId)
    {
        await Groups.RemoveFromGroupAsync(Context.ConnectionId, RentalGroupName(rentalId));
    }
// In RentalHub — replace group logic entirely
    public static async Task NotifyRentalStatusChanged(
        IHubContext<RentalHub> hub,
        int rentalId,
        string userId,        // ← add this param
        string status,
        string? vehicleCode,
        string? dockId)
    {
        await hub.Clients.User(userId).SendAsync("RentalStatusChanged", new { status, vehicleCode, dockId });
    }
}
