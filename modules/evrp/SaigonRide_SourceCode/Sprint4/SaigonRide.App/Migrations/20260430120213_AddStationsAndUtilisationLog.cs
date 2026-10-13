using System;
using Microsoft.EntityFrameworkCore.Migrations;
using Npgsql.EntityFrameworkCore.PostgreSQL.Metadata;

#nullable disable

namespace SaigonRide.Migrations
{
    /// <inheritdoc />
    public partial class AddStationsAndUtilisationLog : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<int>(
                name: "StationId",
                table: "Vehicles",
                type: "integer",
                nullable: true);

            migrationBuilder.AddColumn<int>(
                name: "EndStationId",
                table: "Rentals",
                type: "integer",
                nullable: true);

            migrationBuilder.AddColumn<int>(
                name: "StartStationId",
                table: "Rentals",
                type: "integer",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.CreateTable(
                name: "Stations",
                columns: table => new
                {
                    Id = table.Column<int>(type: "integer", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    Name = table.Column<string>(type: "text", nullable: false),
                    Address = table.Column<string>(type: "text", nullable: false),
                    Latitude = table.Column<double>(type: "double precision", nullable: false),
                    Longitude = table.Column<double>(type: "double precision", nullable: false),
                    Capacity = table.Column<int>(type: "integer", nullable: false),
                    IsActive = table.Column<bool>(type: "boolean", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Stations", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "StationUtilisationLogs",
                columns: table => new
                {
                    Id = table.Column<int>(type: "integer", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    StationId = table.Column<int>(type: "integer", nullable: false),
                    HourSlot = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    BikesAvailable = table.Column<int>(type: "integer", nullable: false),
                    Capacity = table.Column<int>(type: "integer", nullable: false),
                    RentalsStarted = table.Column<int>(type: "integer", nullable: false),
                    RentalsEnded = table.Column<int>(type: "integer", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_StationUtilisationLogs", x => x.Id);
                    table.ForeignKey(
                        name: "FK_StationUtilisationLogs_Stations_StationId",
                        column: x => x.StationId,
                        principalTable: "Stations",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "IX_Vehicles_StationId",
                table: "Vehicles",
                column: "StationId");

            migrationBuilder.CreateIndex(
                name: "IX_Rentals_EndStationId",
                table: "Rentals",
                column: "EndStationId");

            migrationBuilder.CreateIndex(
                name: "IX_Rentals_StartStationId",
                table: "Rentals",
                column: "StartStationId");

            migrationBuilder.CreateIndex(
                name: "IX_StationUtilisationLogs_StationId_HourSlot",
                table: "StationUtilisationLogs",
                columns: new[] { "StationId", "HourSlot" },
                unique: true);
            migrationBuilder.InsertData(
                table: "Stations",
                columns: new[] { "Name", "Address", "Latitude", "Longitude", "Capacity", "IsActive" },
                values: new object[] { "Unknown Station", "N/A", 0.0, 0.0, 0, false }
            );

            migrationBuilder.Sql(
                "UPDATE \"Rentals\" SET \"StartStationId\" = (SELECT \"Id\" FROM \"Stations\" WHERE \"Name\" = 'Unknown Station' LIMIT 1) WHERE \"StartStationId\" = 0;"
            );
            
            migrationBuilder.AddForeignKey(
                name: "FK_Rentals_Stations_EndStationId",
                table: "Rentals",
                column: "EndStationId",
                principalTable: "Stations",
                principalColumn: "Id",
                onDelete: ReferentialAction.Restrict);

            migrationBuilder.AddForeignKey(
                name: "FK_Rentals_Stations_StartStationId",
                table: "Rentals",
                column: "StartStationId",
                principalTable: "Stations",
                principalColumn: "Id",
                onDelete: ReferentialAction.Restrict);

            migrationBuilder.AddForeignKey(
                name: "FK_Vehicles_Stations_StationId",
                table: "Vehicles",
                column: "StationId",
                principalTable: "Stations",
                principalColumn: "Id",
                onDelete: ReferentialAction.SetNull);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_Rentals_Stations_EndStationId",
                table: "Rentals");

            migrationBuilder.DropForeignKey(
                name: "FK_Rentals_Stations_StartStationId",
                table: "Rentals");

            migrationBuilder.DropForeignKey(
                name: "FK_Vehicles_Stations_StationId",
                table: "Vehicles");

            migrationBuilder.DropTable(
                name: "StationUtilisationLogs");

            migrationBuilder.DropTable(
                name: "Stations");

            migrationBuilder.DropIndex(
                name: "IX_Vehicles_StationId",
                table: "Vehicles");

            migrationBuilder.DropIndex(
                name: "IX_Rentals_EndStationId",
                table: "Rentals");

            migrationBuilder.DropIndex(
                name: "IX_Rentals_StartStationId",
                table: "Rentals");

            migrationBuilder.DropColumn(
                name: "StationId",
                table: "Vehicles");

            migrationBuilder.DropColumn(
                name: "EndStationId",
                table: "Rentals");

            migrationBuilder.DropColumn(
                name: "StartStationId",
                table: "Rentals");
        }
    }
}
