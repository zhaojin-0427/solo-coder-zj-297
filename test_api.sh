#!/bin/bash
BASE_URL="http://localhost:9321"

echo "=== 奶粉批次库存与冲泡安全追踪 API 测试 ==="
echo ""

echo "=== 1. 健康检查 ==="
curl -s "$BASE_URL/health" | python3 -m json.tool
echo ""

echo "=== 2. 创建宝宝档案 ==="
BABY_RESPONSE=$(curl -s -X POST "$BASE_URL/api/baby" \
  -H "Content-Type: application/json" \
  -d '{
    "baby_name": "小明",
    "gender": "boy",
    "birth_date": "2025-01-15",
    "current_stage": 2,
    "guardian_name": "张妈妈",
    "guardian_phone": "13800138000"
  }')
echo "$BABY_RESPONSE" | python3 -m json.tool
BABY_ID=$(echo "$BABY_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['baby']['id'])")
echo "宝宝ID: $BABY_ID"
echo ""

echo "=== 3. 添加健康记录（用于分析） ==="
curl -s -X POST "$BASE_URL/api/baby/record" \
  -H "Content-Type: application/json" \
  -d "{
    \"baby_id\": $BABY_ID,
    \"month_age\": 17,
    \"current_stage\": 2,
    \"daily_intake_ml\": 800,
    \"digestion_status\": \"normal\",
    \"weight_kg\": 10.5,
    \"height_cm\": 80
  }" | python3 -m json.tool
echo ""

echo "=== 4. 创建奶粉批次（正常参数） ==="
BATCH_RESPONSE=$(curl -s -X POST "$BASE_URL/api/formula-batches" \
  -H "Content-Type: application/json" \
  -d "{
    \"baby_id\": $BABY_ID,
    \"brand_name\": \"爱他美\",
    \"product_name\": \"卓萃白金版\",
    \"stage\": 2,
    \"batch_number\": \"A202601001\",
    \"opening_date\": \"2026-06-01\",
    \"expiry_date\": \"2027-06-01\",
    \"can_capacity_grams\": 900,
    \"current_remaining_grams\": 900,
    \"storage_method\": \"cool_dry\",
    \"notes\": \"京东自营购买\"
  }")
echo "$BATCH_RESPONSE" | python3 -m json.tool
BATCH_ID=$(echo "$BATCH_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['batch']['id'])")
echo "批次ID: $BATCH_ID"
echo ""

echo "=== 5. 测试异常参数 - 无效段位（5段） ==="
curl -s -X POST "$BASE_URL/api/formula-batches" \
  -H "Content-Type: application/json" \
  -d "{
    \"baby_id\": $BABY_ID,
    \"brand_name\": \"测试品牌\",
    \"product_name\": \"测试产品\",
    \"stage\": 5,
    \"batch_number\": \"TEST001\",
    \"opening_date\": \"2026-06-01\",
    \"expiry_date\": \"2027-06-01\",
    \"can_capacity_grams\": 900,
    \"current_remaining_grams\": 900,
    \"storage_method\": \"cool_dry\"
  }" | python3 -m json.tool
echo ""

echo "=== 6. 测试异常参数 - 未来开封日期 ==="
curl -s -X POST "$BASE_URL/api/formula-batches" \
  -H "Content-Type: application/json" \
  -d "{
    \"baby_id\": $BABY_ID,
    \"brand_name\": \"测试品牌\",
    \"product_name\": \"测试产品\",
    \"stage\": 2,
    \"batch_number\": \"TEST002\",
    \"opening_date\": \"2027-01-01\",
    \"expiry_date\": \"2027-06-01\",
    \"can_capacity_grams\": 900,
    \"current_remaining_grams\": 900,
    \"storage_method\": \"cool_dry\"
  }" | python3 -m json.tool
echo ""

echo "=== 7. 测试异常参数 - 过期批次 ==="
curl -s -X POST "$BASE_URL/api/formula-batches" \
  -H "Content-Type: application/json" \
  -d "{
    \"baby_id\": $BABY_ID,
    \"brand_name\": \"测试品牌\",
    \"product_name\": \"测试产品\",
    \"stage\": 2,
    \"batch_number\": \"TEST003\",
    \"opening_date\": \"2026-01-01\",
    \"expiry_date\": \"2026-01-15\",
    \"can_capacity_grams\": 900,
    \"current_remaining_grams\": 900,
    \"storage_method\": \"cool_dry\"
  }" | python3 -m json.tool
echo ""

echo "=== 8. 查询批次列表（带风险分析） ==="
curl -s "$BASE_URL/api/formula-batches/with-analysis?baby_id=$BABY_ID" | python3 -m json.tool
echo ""

echo "=== 9. 提交冲泡记录（正常参数） ==="
BREWING_RESPONSE=$(curl -s -X POST "$BASE_URL/api/brewing-records" \
  -H "Content-Type: application/json" \
  -d "{
    \"baby_id\": $BABY_ID,
    \"batch_id\": $BATCH_ID,
    \"brewing_time\": \"2026-06-13T09:00:00\",
    \"water_temperature\": 55,
    \"formula_scoops\": 5,
    \"water_volume_ml\": 150,
    \"actual_consumed_ml\": 140,
    \"has_remaining\": true,
    \"remaining_handling\": \"discarded\",
    \"abnormal_notes\": \"无异常\"
  }")
echo "$BREWING_RESPONSE" | python3 -m json.tool
BREWING_ID=$(echo "$BREWING_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['record']['id'])")
echo "冲泡记录ID: $BREWING_ID"
echo ""

echo "=== 10. 提交第二条冲泡记录 ==="
curl -s -X POST "$BASE_URL/api/brewing-records" \
  -H "Content-Type: application/json" \
  -d "{
    \"baby_id\": $BABY_ID,
    \"batch_id\": $BATCH_ID,
    \"brewing_time\": \"2026-06-13T15:00:00\",
    \"water_temperature\": 50,
    \"formula_scoops\": 6,
    \"water_volume_ml\": 180,
    \"actual_consumed_ml\": 180,
    \"has_remaining\": false
  }" | python3 -m json.tool
echo ""

echo "=== 11. 测试异常参数 - 水温过高（80°C） ==="
curl -s -X POST "$BASE_URL/api/brewing-records" \
  -H "Content-Type: application/json" \
  -d "{
    \"baby_id\": $BABY_ID,
    \"batch_id\": $BATCH_ID,
    \"brewing_time\": \"2026-06-13T10:00:00\",
    \"water_temperature\": 80,
    \"formula_scoops\": 5,
    \"water_volume_ml\": 150,
    \"actual_consumed_ml\": 140
  }" | python3 -m json.tool
echo ""

echo "=== 12. 测试异常参数 - 冲泡水量为0 ==="
curl -s -X POST "$BASE_URL/api/brewing-records" \
  -H "Content-Type: application/json" \
  -d "{
    \"baby_id\": $BABY_ID,
    \"batch_id\": $BATCH_ID,
    \"brewing_time\": \"2026-06-13T10:00:00\",
    \"water_temperature\": 55,
    \"formula_scoops\": 5,
    \"water_volume_ml\": 0,
    \"actual_consumed_ml\": 0
  }" | python3 -m json.tool
echo ""

echo "=== 13. 测试异常参数 - 非当前宝宝绑定批次（伪造batch_id=999） ==="
curl -s -X POST "$BASE_URL/api/brewing-records" \
  -H "Content-Type: application/json" \
  -d "{
    \"baby_id\": $BABY_ID,
    \"batch_id\": 999,
    \"brewing_time\": \"2026-06-13T10:00:00\",
    \"water_temperature\": 55,
    \"formula_scoops\": 5,
    \"water_volume_ml\": 150,
    \"actual_consumed_ml\": 140
  }" | python3 -m json.tool
echo ""

echo "=== 14. 查询冲泡安全日报（指定日期 2026-06-13） ==="
curl -s "$BASE_URL/api/brewing-records/daily-report/$BABY_ID?report_date=2026-06-13" | python3 -m json.tool
echo ""

echo "=== 15. 查询库存预警 ==="
curl -s "$BASE_URL/api/brewing-records/batch-stock-warning/$BABY_ID" | python3 -m json.tool
echo ""

echo "=== 16. 更新批次剩余量 ==="
curl -s -X PATCH "$BASE_URL/api/formula-batches/$BATCH_ID/remaining" \
  -H "Content-Type: application/json" \
  -d '{"current_remaining_grams": 800}' | python3 -m json.tool
echo ""

echo "=== 17. 停用批次 ==="
curl -s -X PATCH "$BASE_URL/api/formula-batches/$BATCH_ID/deactivate" | python3 -m json.tool
echo ""

echo "=== 18. 测试使用已停用批次提交冲泡记录（应被拦截） ==="
curl -s -X POST "$BASE_URL/api/brewing-records" \
  -H "Content-Type: application/json" \
  -d "{
    \"baby_id\": $BABY_ID,
    \"batch_id\": $BATCH_ID,
    \"brewing_time\": \"2026-06-13T18:00:00\",
    \"water_temperature\": 55,
    \"formula_scoops\": 5,
    \"water_volume_ml\": 150,
    \"actual_consumed_ml\": 140
  }" | python3 -m json.tool
echo ""

echo "=== 测试完成 ==="
