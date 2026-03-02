# finance/apps.py

from django.apps import AppConfig


class FinanceConfig(AppConfig):
    """
    Конфигурация Django-приложения finance.

    Зачем нужен apps.py:
    - Django использует AppConfig для регистрации приложения
    - тут можно подключать сигналы (ready()), настройки имен, verbose_name
    - удобно держать все "инициализации" приложения в одном месте

    Как подключить:
    - в settings.py добавить:
        INSTALLED_APPS = [
            ...
            "finance.apps.FinanceConfig",
            ...
        ]
      (либо просто "finance", но вариант с AppConfig предпочтительнее)
    """
    default_auto_field = "django.db.models.BigAutoField"
    name = "finance"
    verbose_name = "Финансы"

    def ready(self) -> None:
        """
        Хук, который вызывается при старте Django.

        Обычно здесь импортируют сигналы, чтобы они зарегистрировались:
            from . import signals  # noqa

        Сейчас ничего не подключаем, оставляем пустым для простоты.
        """
        return