from django.db import models


class DailyLeaderSnapshot(models.Model):
    GROUP_WINNER = "winner"
    GROUP_LOSER = "loser"
    GROUP_CHOICES = [
        (GROUP_WINNER, "Winner"),
        (GROUP_LOSER, "Loser"),
    ]

    snapshot_date = models.DateField(db_index=True)
    symbol = models.CharField(max_length=16, db_index=True)
    company_name = models.CharField(max_length=128)
    group = models.CharField(max_length=10, choices=GROUP_CHOICES, db_index=True)
    close_price = models.DecimalField(max_digits=12, decimal_places=2)
    change_pct = models.DecimalField(max_digits=7, decimal_places=2)
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("snapshot_date", "symbol", "group"),)
        ordering = ["-snapshot_date", "group", "symbol"]

