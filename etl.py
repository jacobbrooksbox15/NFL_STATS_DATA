import os
import pandas as pd
import nflreadpy as nfl

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

SEASON = 2026

print("1. Fetching NFLverse datasets...")
raw_stats = nfl.load_player_stats(seasons=[SEASON])
raw_rosters = nfl.load_rosters(seasons=[SEASON])
raw_sched = nfl.load_schedules(seasons=[SEASON])

# Ensure DataFrames are standard pandas
df_stats = raw_stats.to_pandas() if hasattr(raw_stats, "to_pandas") else pd.DataFrame(raw_stats)
df_rosters = raw_rosters.to_pandas() if hasattr(raw_rosters, "to_pandas") else pd.DataFrame(raw_rosters)
df_sched = raw_sched.to_pandas() if hasattr(raw_sched, "to_pandas") else pd.DataFrame(raw_sched)

print("2. Building Dim_Player...")
pos_list = ["QB", "RB", "WR", "TE", "K"]
dim_player = df_rosters[df_rosters["position"].isin(pos_list)].copy()

# Standardize column names (gsis_id -> player_id, full_name -> player_name)
rename_map = {
    "gsis_id": "player_id",
    "full_name": "player_name"
}
dim_player = dim_player.rename(columns=rename_map)

# Keep standard player columns
player_cols = ["player_id", "player_name", "position", "team", "status", "headshot_url"]
dim_player = dim_player[[c for c in player_cols if c in dim_player.columns]]
dim_player = dim_player.dropna(subset=["player_id"]).drop_duplicates(subset=["player_id"])

print("3. Building Dim_Schedule...")
sched_cols = ["game_id", "season", "week", "game_type", "gameday", "home_team", "away_team", "home_score", "away_score"]
dim_schedule = df_sched[[c for c in sched_cols if c in df_sched.columns]].drop_duplicates(subset=["game_id"])

print("4. Building Fact_WeeklyStats...")
stat_cols = [
    "game_id",
    "player_id", "season", "week", "recent_team", "opponent_team",
    "completions", "attempts", "passing_yards", "passing_tds", "interceptions",
    "carries", "rushing_yards", "rushing_tds",
    "receptions", "targets", "receiving_yards", "receiving_tds",
    "sack_fumbles_lost", "rushing_fumbles_lost", "receiving_fumbles_lost"
]
existing_cols = [c for c in stat_cols if c in df_stats.columns]
fact_weekly = df_stats[existing_cols].fillna(0)

# Fallback: if game_id is missing from load_player_stats, match it from dim_schedule
if "game_id" not in fact_weekly.columns:
    sched_lookup = (
        pd.concat([
            df_sched[["game_id", "season", "week", "home_team"]].rename(columns={"home_team": "recent_team"}),
            df_sched[["game_id", "season", "week", "away_team"]].rename(columns={"away_team": "recent_team"})
        ])
        .drop_duplicates(subset=["season", "week", "recent_team"])
    )
    fact_weekly = fact_weekly.merge(sched_lookup, on=["season", "week", "recent_team"], how="left")

# Sum total fumbles lost
fumble_cols = [c for c in ["sack_fumbles_lost", "rushing_fumbles_lost", "receiving_fumbles_lost"] if c in fact_weekly.columns]
fact_weekly["fumbles_lost"] = fact_weekly[fumble_cols].sum(axis=1)

print("5. Building Fact_Projections (Baseline Rolling Averages)...")
numeric_metrics = [
    "passing_yards", "passing_tds", "interceptions", 
    "rushing_yards", "rushing_tds", "receptions", 
    "receiving_yards", "receiving_tds", "fumbles_lost"
]
existing_metrics = [c for c in numeric_metrics if c in fact_weekly.columns]

fact_proj = fact_weekly.groupby("player_id")[existing_metrics].mean().reset_index()
fact_proj["projected_season"] = SEASON

print("6. Exporting CSV files to /data...")
dim_player.to_csv(f"{DATA_DIR}/Dim_Player.csv", index=False)
dim_schedule.to_csv(f"{DATA_DIR}/Dim_Schedule.csv", index=False)
fact_weekly.to_csv(f"{DATA_DIR}/Fact_WeeklyStats.csv", index=False)
fact_proj.to_csv(f"{DATA_DIR}/Fact_Projections.csv", index=False)

print("ETL complete! All Star Schema CSVs generated successfully.")