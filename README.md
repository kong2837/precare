# 중견연구 전용 웹

## 개발 환경
```
OS: Ubuntu 20.04
Python: 3.11.3
```

## Settings

### settgins.py

#### DATABASE

MariaDB에서 사용할 `USERNAME` 과 `PASSWORD`, 데이터 베이스 이름(`NAME`) 등을 설정합니다.

```python
# settings.py
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "apopdb",
        "USER": "example-user", 
        "PASSWORD": "example-password", 
        "HOST": "mariadb",
        "PORT": "3306"
    },
}
```

#### CSRF_TRUSTED_ORIGINS

배포할 서버의 주소로 바꿔줍니다.

```python
CSRF_TRUSTED_ORIGINS = ['http://*.YOUR_DOMAIN.COM']
```

#### AUTH_KEY

API 키를 적절히 수정합니다.

```python
AUTH_KEY = 1234 
```

### docker-compose.yml

#### Nginx

개방할 포트를 선택합니다.

```yaml
  nginx:
    image: nginx:1.25.3
    networks:
      - network
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./static:/data/static
    ports:
      - 80:80 # 만약 외부에 8080 등으로 열고 싶다면 8080:80으로 설정
    depends_on:
      - apop
```

## Install

```shell
docker compose up --build -d
```

### createsuperuser
django에서 superuser를 만들기 위해서 아래의 명령어를 수행합니다.

```shell
docker exec -it apop python manage.py createsuperuser
```


### 이후부터는 코드에 관한 정보입니다.
###
common 파일에 urls,view,form 웹페이지 다루는 파일 존재.