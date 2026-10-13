using System;
using System.Collections.Generic;
using System.Linq;
using SaigonRide.App.Models.Entities;

namespace SaigonRide.App.Services
{
    public class EvrpSolverService
    {
        // EVRP Vehicle Config
        public const int VehicleCapacity = 10;
        public const double BatteryDischargePerKm = 8.0; // 8% battery used per km
        public const double BatteryChargeThreshold = 20.0; // Recharge if battery falls below 20%

        public class EvrpNode
        {
            public int Id { get; set; }
            public string Name { get; set; } = string.Empty;
            public double Latitude { get; set; }
            public double Longitude { get; set; }
            public int Capacity { get; set; }
            public int InitialAvailable { get; set; }
            public int Target { get; set; }
            public int Demand => Target - CurrentAvailable;
            public int CurrentAvailable { get; set; }
        }

        public class RouteStep
        {
            public int Sequence { get; set; }
            public int StationId { get; set; }
            public string StationName { get; set; } = string.Empty;
            public string Action { get; set; } = string.Empty; // "Start", "Load", "Unload", "Recharge", "End"
            public int BikesTransferred { get; set; }
            public int VehicleLoadAfter { get; set; }
            public double VehicleBatteryAfter { get; set; }
            public double StepDistance { get; set; }
            public double CumulativeDistance { get; set; }
            public double Latitude { get; set; }
            public double Longitude { get; set; }
        }

        public class EvrpSolution
        {
            public List<RouteStep> Steps { get; set; } = new List<RouteStep>();
            public double TotalDistance { get; set; }
            public double BatteryUsed { get; set; }
            public int BikesMoved { get; set; }
            public bool IsFeasible { get; set; }
        }

        public double CalculateDistance(double lat1, double lon1, double lat2, double lon2)
        {
            const double R = 6371.0; // Earth's radius in km
            var dLat = ToRadians(lat2 - lat1);
            var dLon = ToRadians(lon2 - lon1);
            var a = Math.Sin(dLat / 2) * Math.Sin(dLat / 2) +
                    Math.Cos(ToRadians(lat1)) * Math.Cos(ToRadians(lat2)) *
                    Math.Sin(dLon / 2) * Math.Sin(dLon / 2);
            var c = 2 * Math.Atan2(Math.Sqrt(a), Math.Sqrt(1 - a));
            return R * c;
        }

        private double ToRadians(double val) => (Math.PI / 180.0) * val;

        public EvrpSolution Solve(List<Station> stations, Dictionary<int, int> currentAvailableMap, int depotId)
        {
            // 1. Prepare nodes
            var nodes = stations.Select(s => new EvrpNode
            {
                Id = s.Id,
                Name = s.Name,
                Latitude = s.Latitude,
                Longitude = s.Longitude,
                Capacity = s.Capacity,
                InitialAvailable = currentAvailableMap.GetValueOrDefault(s.Id, 0),
                Target = s.Capacity / 2, // Ideal balance state is 50% capacity
                CurrentAvailable = currentAvailableMap.GetValueOrDefault(s.Id, 0)
            }).ToList();

            var depot = nodes.FirstOrDefault(n => n.Id == depotId) ?? nodes.First();

            // 2. Greedy Construction of sequence of visited nodes
            var visitedSequence = new List<EvrpNode> { depot };
            var activeNodes = nodes.Where(n => n.Id != depot.Id).ToList();

            var current = depot;
            int load = 0;
            double battery = 100.0;

            // Keep track of simulator node state during route construction
            var tempBikes = nodes.ToDictionary(n => n.Id, n => n.CurrentAvailable);

            while (true)
            {
                // Find next node to visit
                EvrpNode? nextNode = null;
                double bestDist = double.MaxValue;

                foreach (var node in activeNodes)
                {
                    int nodeTarget = node.Capacity / 2;
                    int nodeDemand = nodeTarget - tempBikes[node.Id];

                    // Check if node needs service
                    bool canService = false;
                    if (nodeDemand < 0 && load < VehicleCapacity) // Donor, we have capacity to pick up
                    {
                        canService = true;
                    }
                    else if (nodeDemand > 0 && load > 0) // Recipient, we have bikes to drop off
                    {
                        canService = true;
                    }

                    if (canService)
                    {
                        double d = CalculateDistance(current.Latitude, current.Longitude, node.Latitude, node.Longitude);
                        if (d < bestDist)
                        {
                            bestDist = d;
                            nextNode = node;
                        }
                    }
                }

                if (nextNode == null)
                {
                    // No more nodes to service, return to depot
                    break;
                }

                // Simulate travel
                double travelDist = bestDist;
                double batteryUsed = travelDist * BatteryDischargePerKm;

                // Battery guard: if moving to nextNode and back to depot causes battery to drop below threshold, force a recharge
                double distBackToDepot = CalculateDistance(nextNode.Latitude, nextNode.Longitude, depot.Latitude, depot.Longitude);
                double totalDistFromHere = travelDist + distBackToDepot;
                double totalBatteryNeeded = totalDistFromHere * BatteryDischargePerKm;

                if (battery - totalBatteryNeeded < BatteryChargeThreshold)
                {
                    // Recharge at the current station before traveling
                    battery = 100.0;
                }

                // Move to next station
                current = nextNode;
                battery -= batteryUsed;
                visitedSequence.Add(nextNode);

                // Service the node
                int demand = nextNode.Capacity / 2 - tempBikes[nextNode.Id];
                if (demand < 0) // Donor
                {
                    int space = VehicleCapacity - load;
                    int toLoad = Math.Min(space, -demand);
                    load += toLoad;
                    tempBikes[nextNode.Id] += toLoad;
                }
                else if (demand > 0) // Recipient
                {
                    int toUnload = Math.Min(load, demand);
                    load -= toUnload;
                    tempBikes[nextNode.Id] -= toUnload;
                }

                // If battery fell low, we can recharge after servicing
                if (battery < BatteryChargeThreshold)
                {
                    battery = 100.0;
                }
            }

            // Return to depot
            visitedSequence.Add(depot);

            // 3. Optimize sequence via 2-Opt local search
            var optimizedSequence = Optimize2Opt(visitedSequence, depot);

            // 4. Build detailed final steps from the optimized sequence
            return EvaluateSequence(optimizedSequence, nodes, depotId);
        }

        private List<EvrpNode> Optimize2Opt(List<EvrpNode> sequence, EvrpNode depot)
        {
            if (sequence.Count <= 3) return sequence;

            var bestSeq = new List<EvrpNode>(sequence);
            double bestDist = CalculateRouteDistance(bestSeq);
            bool improved = true;

            int limit = 0;
            while (improved && limit < 100)
            {
                improved = false;
                limit++;

                for (int i = 1; i < bestSeq.Count - 2; i++)
                {
                    for (int j = i + 1; j < bestSeq.Count - 1; j++)
                    {
                        var newSeq = TwoOptSwap(bestSeq, i, j);
                        double newDist = CalculateRouteDistance(newSeq);

                        if (newDist < bestDist - 0.0001)
                        {
                            bestSeq = newSeq;
                            bestDist = newDist;
                            improved = true;
                        }
                    }
                }
            }

            return bestSeq;
        }

        private List<EvrpNode> TwoOptSwap(List<EvrpNode> route, int i, int j)
        {
            var newRoute = new List<EvrpNode>();
            // 1. Take route[0] to route[i-1]
            for (int k = 0; k < i; k++)
            {
                newRoute.Add(route[k]);
            }
            // 2. Take route[i] to route[j] and reverse them
            for (int k = j; k >= i; k--)
            {
                newRoute.Add(route[k]);
            }
            // 3. Take route[j+1] to end
            for (int k = j + 1; k < route.Count; k++)
            {
                newRoute.Add(route[k]);
            }
            return newRoute;
        }

        private double CalculateRouteDistance(List<EvrpNode> route)
        {
            double dist = 0;
            for (int i = 0; i < route.Count - 1; i++)
            {
                dist += CalculateDistance(route[i].Latitude, route[i].Longitude, route[i+1].Latitude, route[i+1].Longitude);
            }
            return dist;
        }

        private EvrpSolution EvaluateSequence(List<EvrpNode> sequence, List<EvrpNode> originalNodes, int depotId)
        {
            var nodes = originalNodes.ToDictionary(n => n.Id, n => new EvrpNode
            {
                Id = n.Id,
                Name = n.Name,
                Latitude = n.Latitude,
                Longitude = n.Longitude,
                Capacity = n.Capacity,
                InitialAvailable = n.InitialAvailable,
                Target = n.Target,
                CurrentAvailable = n.InitialAvailable
            });

            var steps = new List<RouteStep>();
            double cumDist = 0.0;
            int load = 0;
            double battery = 100.0;
            int bikesMoved = 0;
            int stepSeq = 1;

            var first = sequence.First();
            steps.Add(new RouteStep
            {
                Sequence = stepSeq++,
                StationId = first.Id,
                StationName = first.Name,
                Action = "Start",
                BikesTransferred = 0,
                VehicleLoadAfter = load,
                VehicleBatteryAfter = battery,
                StepDistance = 0.0,
                CumulativeDistance = 0.0,
                Latitude = first.Latitude,
                Longitude = first.Longitude
            });

            for (int i = 1; i < sequence.Count; i++)
            {
                var prev = sequence[i - 1];
                var curr = sequence[i];

                double d = CalculateDistance(prev.Latitude, prev.Longitude, curr.Latitude, curr.Longitude);
                cumDist += d;
                battery -= d * BatteryDischargePerKm;

                // Check battery charging triggers
                if (battery < BatteryChargeThreshold)
                {
                    // Add recharge event before servicing current station
                    steps.Add(new RouteStep
                    {
                        Sequence = stepSeq++,
                        StationId = curr.Id,
                        StationName = curr.Name,
                        Action = "Recharge",
                        BikesTransferred = 0,
                        VehicleLoadAfter = load,
                        VehicleBatteryAfter = 100.0,
                        StepDistance = d,
                        CumulativeDistance = cumDist,
                        Latitude = curr.Latitude,
                        Longitude = curr.Longitude
                    });
                    battery = 100.0;
                }

                // Service station
                var node = nodes[curr.Id];
                int demand = node.Target - node.CurrentAvailable;
                int transfer = 0;
                string action = "Visit";

                if (demand < 0) // Donor: pick up surplus bikes
                {
                    int space = VehicleCapacity - load;
                    transfer = Math.Min(space, -demand);
                    load += transfer;
                    node.CurrentAvailable += transfer;
                    action = "Load";
                    bikesMoved += transfer;
                }
                else if (demand > 0) // Recipient: drop off bikes
                {
                    transfer = Math.Min(load, demand);
                    load -= transfer;
                    node.CurrentAvailable -= transfer;
                    action = "Unload";
                }

                steps.Add(new RouteStep
                {
                    Sequence = stepSeq++,
                    StationId = curr.Id,
                    StationName = curr.Name,
                    Action = i == sequence.Count - 1 ? "End" : action,
                    BikesTransferred = transfer,
                    VehicleLoadAfter = load,
                    VehicleBatteryAfter = battery,
                    StepDistance = d,
                    CumulativeDistance = cumDist,
                    Latitude = curr.Latitude,
                    Longitude = curr.Longitude
                });
            }

            return new EvrpSolution
            {
                Steps = steps,
                TotalDistance = cumDist,
                BatteryUsed = 100.0 - battery,
                BikesMoved = bikesMoved,
                IsFeasible = battery >= 0
            };
        }
    }
}
