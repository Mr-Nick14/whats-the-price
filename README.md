# What's Price

Сервис оценки цены подержанного автомобиля на FastAPI. Структура основана на первом
семинаре, но вместо классификации оттока здесь регрессия. Обучение и сравнение с
`DummyRegressor` находятся в [ноутбуке](notebooks/01_baseline.ipynb). Модель и её
метаданные сохранены в `artifacts/model.joblib`.

## Семинар 3: MLflow и DVC

Ветка `sem3` содержит подготовку к работе с реестром моделей. Без `MODEL_NAME` API
по-прежнему загружает локальный `artifacts/model.joblib`. При заданном `MODEL_NAME`
он на старте загружает `models:/<MODEL_NAME>@champion` из MLflow; `/health`
показывает номер версии реестра и URI модели. Для отката смените алиас `champion`
в MLflow и перезапустите поды сервиса.

Исходный CSV домашки 1 остаётся локальным. Выборка для DVC была создана по
`listing_id % 12 == 0`; в новом клоне её восстанавливают командой:

```bash
uv run dvc pull
```

Для повторного создания выборки из исходного CSV используйте
`PYTHONPATH=src uv run python scripts/prepare_data.py` в рабочем каталоге,
где файла `data/used_cars_sample.csv` ещё нет.

Выборка `data/used_cars_sample.csv` отслеживается DVC, а локальное хранилище
настроено по соседнему пути `../dvc-storage`. Новому клону потребуется доступ к
этой папке. Для обучения задайте адрес MLflow и запустите скрипт:

```bash
export MLFLOW_TRACKING_URI=http://mlflow.localhost
PYTHONPATH=src uv run python scripts/train.py --data-path data/used_cars_sample.csv
```

Скрипт записывает `data_md5`, validation MAE, `metadata.json`, график остатков
и новую версию `what-s-price`. Новая версия получает `challenger`. Алиас
`champion` переходит на неё, если MAE улучшился минимум на 100 долларов; первая
версия становится `champion` без сравнения.

Файлы локальной платформы лежат в `platform/` и `k8s/`. После запуска Docker
Desktop и установки `helm` команда `bash scripts/setup-sem3-cluster.sh` создаёт
отдельный кластер `ml-pro-sem3` с портом 80, ставит Traefik и metrics-server,
разворачивает MLflow. Затем нужно обучить хотя бы одну модель в этом MLflow:
сервис в режиме реестра не стартует без `champion`.

Для CI job `deploy` теперь назначен runner с метками `self-hosted` и `kind`.
Готовый образ в `platform/runner/` содержит `kind`, `kubectl` и `python3`.
После создания секрета GitHub Actions `DB_PASSWORD` откройте Settings → Actions →
Runners → New self-hosted runner, скопируйте временный registration token и
запустите:

```bash
RUNNER_TOKEN='<временный токен>' bash scripts/start-sem3-runner.sh
```

Скрипт запускает runner в Docker-сети `kind`, подключает Docker socket и временный
kubeconfig с адресом `ml-pro-sem3-control-plane:6443`. Для работы с внешними
contributions включите в Settings → Actions → General требование одобрения
workflow от новых авторов. После проверки остановите контейнер `gh-runner`,
удалите его в Docker и удалите временный kubeconfig, путь к которому напечатал
скрипт. Runner также следует удалить в Settings → Actions → Runners.

Smoke из runner обращается к Ingress через имя control-plane с заголовком
`Host: price.localhost`. Локально его можно повторить командой
`INGRESS_URL=http://price.localhost bash scripts/sem3-smoke.sh`.

## Проверка

Нужны `uv`, Docker, `kind`, `kubectl` и `curl`. Из корня репозитория выполните три команды.

```bash
uv run pytest -q
docker compose up -d --build
bash scripts/kind-smoke.sh
```

API работает на `http://127.0.0.1:8000`. Схема доступна в `/docs`, пример запроса в
[good.json](good.json). Проверки состояния находятся в `/health` и `/ready`, прогноз в
`POST /v1/predict`.

Compose запускает API и PostgreSQL. Таблица `predictions` хранит запросы со статусами
`200`, `422` и `500`. Скрипт `kind-smoke.sh` разворачивает две реплики API и проверяет
прогноз через port-forward.

Дополнительные задания включают пакетный прогноз до 1000 машин и нагрузочный тест Locust.
Результаты и скриншоты находятся в [отчёте](REPORT.md).

## CI для ДЗ2

Pull request запускает `ruff` и `pytest` с PostgreSQL. Push в `develop` или `main`
также собирает образ с тегом `sha-<commit>` в GHCR и проверяет его в `kind`.
Для деплоя нужен секрет репозитория `DB_PASSWORD`:
GitHub → Settings → Secrets and variables → Actions. Используйте пароль без
символов, требующих кодирования в URL.

`/health` показывает путь к модели из ConfigMap. CI smoke проверяет этот путь,
диапазон цены для `good.json` и запись запроса в PostgreSQL. Ссылки на прогоны
и разбор ошибок будут в [отчёте](REPORT.md).
