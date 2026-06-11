from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from database import engine, Base
from routers import baby, analysis, doctor
from schemas import ApiResponse

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="妈妈奶粉段位转换与宝宝月龄适配分析 API",
    description="提供宝宝档案管理、段位匹配、营养建议、转段预警、医生咨询等服务",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ApiResponse(
            code=400,
            message="参数校验失败",
            data={"details": exc.errors()},
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ApiResponse(
            code=500,
            message=f"服务器内部错误: {str(exc)}",
            data=None,
        ).model_dump(),
    )


@app.get("/", response_model=ApiResponse)
def root():
    return ApiResponse(
        code=200,
        message="服务运行正常",
        data={
            "name": "妈妈奶粉段位转换与宝宝月龄适配分析 API",
            "version": "1.0.0",
            "docs": "/docs",
            "endpoints": {
                "宝宝档案": "/api/baby",
                "段位匹配": "/api/analysis/stage-match",
                "营养建议": "/api/analysis/nutrition",
                "转段预警": "/api/analysis/transition-warning",
                "段位参考": "/api/analysis/stages",
                "医生咨询": "/api/doctor/consultation",
            },
        },
    )


@app.get("/health", response_model=ApiResponse)
def health_check():
    return ApiResponse(code=200, message="健康检查通过", data={"status": "ok"})


app.include_router(baby.router)
app.include_router(analysis.router)
app.include_router(doctor.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=9321, reload=True)
