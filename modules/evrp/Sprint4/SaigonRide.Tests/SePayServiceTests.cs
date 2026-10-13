using Microsoft.Extensions.Configuration;
using SaigonRide.App.Services;
using FluentAssertions;

namespace SaigonRide.Tests;

public class SepayServiceTests
{
    private static SepayService BuildService() =>
        new(new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?> {
                ["Sepay:BankId"]        = "bidv",
                ["Sepay:AccountNumber"] = "1234567890",
                ["Sepay:AccountName"]   = "SAIGONRIDE",
                ["Sepay:Template"]      = "compact2"
            }).Build());

    [Fact]
    public void GenerateQrUrl_ContainsBankAndAccount()
    {
        var url = BuildService().GenerateQrUrl(500_000m, rentalId: 42);
        url.Should().Contain("bidv-1234567890");
        url.Should().Contain("amount=500000");
        url.Should().Contain("SGR");
    }

    [Fact]
    public void GenerateWalletTopUpQrUrl_ContainsSGRW()
    {
        var url = BuildService().GenerateWalletTopUpQrUrl(100_000m, transactionId: 7);
        url.Should().Contain("SGRW");
        url.Should().Contain("amount=100000");
    }
}