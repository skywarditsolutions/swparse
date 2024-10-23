ARG PYTHON_BUILDER_IMAGE=3.12-bookworm

## ---------------------------------------------------------------------------------- ##
## ------------------------- Python base -------------------------------------------- ##
## ---------------------------------------------------------------------------------- ##
FROM python:${PYTHON_BUILDER_IMAGE} as python-base
ENV PIP_DEFAULT_TIMEOUT=100 \
  PIP_DISABLE_PIP_VERSION_CHECK=1 \
  PIP_NO_CACHE_DIR=1 \
  PIP_ROOT_USER_ACTION=ignore \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONFAULTHANDLER=1 \
  PYTHONHASHSEED=random \
  LANG=C.UTF-8 \
  LC_ALL=C.UTF-8
RUN apt-get update \
  && apt-get upgrade -y \
  && apt-get install -y --no-install-recommends git tini \
  && apt-get autoremove -y \
  && apt-get clean -y \
  && rm -rf /root/.cache \
  && rm -rf /var/apt/lists/* \
  && rm -rf /var/cache/apt/* \
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false\
  && mkdir -p /workspace/swparse \
  && pip install --quiet -U pip wheel setuptools virtualenv
RUN pip install -U pdm

## ---------------------------------------------------------------------------------- ##
## ------------------------- Python build base -------------------------------------- ##
## ---------------------------------------------------------------------------------- ##
## -------------------------- add build packages ----------------------------------- ##
RUN apt-get install -y --no-install-recommends build-essential curl

## -------------------------- install application ----------------------------------- ##
COPY pyproject.toml pdm.lock README.md .pre-commit-config.yaml Makefile /workspace/swparse/
COPY scripts /workspace/swparse/scripts/
WORKDIR /workspace/swparse
RUN pdm install --check --prod --no-editable

## ---------------------------------------------------------------------------------- ##
## -------------------------------- development build ------------------------------- ##
## ---------------------------------------------------------------------------------- ##
## ------------------------- use builder base --------------------------------------- ##
FROM python-base as dev-image
ARG ENV_SECRETS="runtime-secrets"
ARG LITESTAR_APP="swparse.asgi:swparse"
## --------------------------- standardize execution env ----------------------------- ##
ENV PATH="/workspace/swparse/.venv/bin:$PATH" \
  VIRTUAL_ENV="/workspace/swparse/.venv" \
  ENV_SECRETS="${ENV_SECRETS}"  \
  PIP_DEFAULT_TIMEOUT=100 \
  PIP_DISABLE_PIP_VERSION_CHECK=1 \
  PIP_NO_CACHE_DIR=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONFAULTHANDLER=1 \
  PYTHONHASHSEED=random \
  LANG=C.UTF-8 \
  LC_ALL=C.UTF-8 \
  LITESTAR_APP="${LITESTAR_APP}"
WORKDIR /workspace/swparse
COPY tests/ tests/
COPY src src/
COPY deploy deploy/
RUN apt-get update && apt-get install -y libgl-dev
RUN pdm install $PDM_INSTALL_ARGS
STOPSIGNAL SIGINT
EXPOSE 8000
ENTRYPOINT ["tini","--" ]
CMD [ "litestar","run","--host","0.0.0.0"]
VOLUME /workspace/swparse
