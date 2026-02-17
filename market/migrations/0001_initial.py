from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DailyLeaderSnapshot",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("snapshot_date", models.DateField(db_index=True)),
                ("symbol", models.CharField(db_index=True, max_length=16)),
                ("company_name", models.CharField(max_length=128)),
                (
                    "group",
                    models.CharField(
                        choices=[("winner", "Winner"), ("loser", "Loser")],
                        db_index=True,
                        max_length=10,
                    ),
                ),
                ("close_price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("change_pct", models.DecimalField(decimal_places=2, max_digits=7)),
                ("captured_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-snapshot_date", "group", "symbol"],
                "unique_together": {("snapshot_date", "symbol", "group")},
            },
        ),
    ]

