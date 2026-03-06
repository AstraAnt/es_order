from django.db import models


class OrderNumberCounter(models.Model):
    """
    Счётчик номеров заказов по префиксу.

    Пример префикса:
        NK_SR_06.03.26

    last_number хранит последнее выданное число для этого префикса:
    - 1  -> код без суффикса: NK_SR_06.03.26
    - 2  -> NK_SR_06.03.26_2
    - 3  -> NK_SR_06.03.26_3

    Почему нужна отдельная таблица:
    - count() по заказам не атомарен под конкуренцией
    - отдельный счётчик позволяет безопасно и быстро выдавать следующий номер
    - для PostgreSQL это особенно хорошо работает с UPSERT + RETURNING
    """

    # Префикс сам по себе уникален, поэтому делаем его primary key
    prefix = models.CharField(max_length=64, primary_key=True)

    # Последний выданный номер для префикса
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Счётчик номера заказа"
        verbose_name_plural = "Счётчики номеров заказов"

    def __str__(self) -> str:
        return f"{self.prefix} -> {self.last_number}"