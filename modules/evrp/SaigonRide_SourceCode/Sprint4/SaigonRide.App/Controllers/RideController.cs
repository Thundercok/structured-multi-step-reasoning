using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using SaigonRide.App.Models.ViewModels;
using SaigonRide.App.Services;
using Microsoft.AspNetCore.Authentication.JwtBearer;
    
namespace SaigonRide.App.Controllers;

[ApiController]
[Route("api/ride")]
[Authorize(AuthenticationSchemes = JwtBearerDefaults.AuthenticationScheme)]
public class RideController : ControllerBase
{
    private readonly RideService _rideService;

    public RideController(RideService rideService)
    {
        _rideService = rideService;
    }

    [HttpPost("start")]
    public async Task<IActionResult> Start([FromBody] RideStartRequest request, CancellationToken cancellationToken)
    {
        var userId = User.FindFirstValue(ClaimTypes.NameIdentifier);
        if (userId == null) return Unauthorized();

        try
        {
            var response = await _rideService.StartRideAsync(userId, request, cancellationToken);
            return Ok(response);
        }
        catch (InvalidOperationException ex) when (ex.Message == "Insufficient Funds")
        {
            return BadRequest(new { message = "Insufficient Funds", minimumBalance = RideService.MinimumStartBalance });
        }
        catch (InvalidOperationException ex)
        {
            return BadRequest(new { message = ex.Message });
        }
    }

    [HttpPost("stop")]
    public async Task<IActionResult> Stop([FromBody] RideStopRequest request, CancellationToken cancellationToken)
    {
        var userId = User.FindFirstValue(ClaimTypes.NameIdentifier);
        if (userId == null) return Unauthorized();

        try
        {
            var response = await _rideService.StopRideAsync(userId, request, cancellationToken);
            return Ok(response);
        }
        catch (InvalidOperationException ex) when (ex.Message == "Insufficient Funds")
        {
            return BadRequest(new { message = "Insufficient Funds", minimumAllowedBalance = RideService.MinimumAllowedBalance });
        }
        catch (InvalidOperationException ex)
        {
            return BadRequest(new { message = ex.Message });
        }
    }
}
