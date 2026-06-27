# Data Acquisition Tool

에세텔이 개발한 데이터 수집 도구임

Documentation is available in both English and Korean.

- [README_ENG.md](README_ENG.md)
- [README_KOR.md](README_KOR.md)
- [docs/USER_MANUAL_ENG.md](docs/USER_MANUAL_ENG.md)
- [docs/USER_MANUAL_KOR.md](docs/USER_MANUAL_KOR.md)


### Github 소스코드 등록
```
> git init
> git remote add origin https://github.com/KyounghyunPark/data_acquisition.git
> touh .gitignore
> git add .
> git status
> git commit -m "initial commit"
> git push origin main
```

### Installation
- mariadb 설치
  ```
  >  brew install mariadb
  >  brew services start mariadb
  ```
- 가상환경 구축
  ```
  > python -m venv .venv
  > source .venv/bin/activate
  ```
- 패키지 설치
  ```
  > python -m pip install --upgrade pip
  > pip install -r requirements.txt
  ```
- DB 생성
  ```
  > mysql -uroot -e "CREATE DATABASE daegu_local DEFAULT CHARACTER SET euckr COLLATE euckr_korean_ci;"
  > mysql -uroot daegu_local < sql_data/20260601_daegu_test.sql
  ```
