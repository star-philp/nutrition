import { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [recipes, setRecipes] = useState([]);
  const [error, setError] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [predictions, setPredictions] = useState([]);
  const [uploading, setUploading] = useState(false);

  // 사용자가 선택한 레시피와 섭취량 상태 추가
  const [selectedRecipe, setSelectedRecipe] = useState(null);
  const [portion, setPortion] = useState(null);
  const [finalNutrition, setFinalNutrition] = useState(null);

  // 식단 일지 관련 상태
  const [viewMode, setViewMode] = useState('analysis'); // 'analysis' or 'log'
  const [mealLogs, setMealLogs] = useState([]);
  const [dailySummary, setDailySummary] = useState([]);
  const [analysisDate, setAnalysisDate] = useState('');
  const [analysisResult, setAnalysisResult] = useState(null);
  // RAG 검색 상태
  const [ragQuery, setRagQuery] = useState('');
  const [ragResults, setRagResults] = useState([]);
  const [ragAnswer, setRagAnswer] = useState(null);
  const [ragLoading, setRagLoading] = useState(false);
  const [ragError, setRagError] = useState(null);


  // 레시피 목록 불러오기
  useEffect(() => {
    axios.get('http://localhost:8080/api/v1/recipes')
      .then(response => {
        console.log("API로부터 받은 레시피 데이터:", response.data);
        setRecipes(response.data);
      })
      .catch(error => {
        console.error('레시피 데이터를 불러오는 중 오류 발생:', error);
        setError('데이터를 불러올 수 없습니다. 백엔드 서버가 실행 중인지 확인해 주세요.');
      });
  }, []);

  // 식단 일지 데이터 불러오기
  const fetchMealLogs = async () => {
    try {
      const response = await axios.get('http://localhost:8080/api/v1/users/1/meal-logs/'); // user_id=1은 임시
      setMealLogs(response.data);
    } catch (error) {
      console.error('식단 기록을 불러오는 중 오류 발생:', error);
      setError('식단 기록을 불러올 수 없습니다.');
    }
  };

  const fetchDailySummary = async () => {
    try {
      const response = await axios.get('http://localhost:8080/api/v1/users/1/daily-summary');
      setDailySummary(response.data);
    } catch (error) {
      console.error('일일 합계를 불러오는 중 오류 발생:', error);
    }
  };

  // 일일 합계가 로드되면 기본 분석 날짜를 최신 날짜로 설정
  useEffect(() => {
    if (!analysisDate && dailySummary && dailySummary.length > 0) {
      setAnalysisDate(dailySummary[0].date);
    }
  }, [dailySummary]);

  const handleAnalyzeDaily = async () => {
    if (!analysisDate) return;
    try {
      const res = await axios.post('http://localhost:8080/api/v1/analysis/daily', {
        user_id: 1,
        date: analysisDate
      });
      setAnalysisResult(res.data);
    } catch (err) {
      console.error('일일 분석 호출 실패:', err);
      setError('일일 분석에 실패했습니다.');
    }
  };

  // RAG 검색 호출
  const handleRagSearch = async () => {
    const q = (ragQuery || '').trim();
    if (!q) return;
    setRagLoading(true);
    setRagError(null);
    setRagAnswer(null);
    try {
      const res = await axios.post('http://localhost:8080/api/v1/rag/search', {
        query: q,
        top_k: 5,
      });
      setRagAnswer(res.data?.answer || null);
      setRagResults(res.data?.sources || []);
    } catch (e) {
      console.error('RAG 검색 실패:', e);
      setRagError('검색에 실패했습니다. 서버 상태를 확인해 주세요.');
    } finally {
      setRagLoading(false);
    }
  };


  // 파일 선택 시 미리보기 생성
  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      setSelectedFile(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setPreview(reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

  // 이미지 업로드 및 분석 요청
  const handleUpload = async () => {
    if (!selectedFile) return;

    setUploading(true);
    setPredictions([]);
    setError(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await axios.post('http://localhost:8080/api/v1/predict', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setPredictions(response.data.predictions);
    } catch (error) {
      console.error('이미지 분석 중 오류 발생:', error);
      setError('이미지 분석에 실패했습니다. 다시 시도해 주세요.');
    } finally {
      setUploading(false);
    }
  };

  // AI 추천 레시피를 사용자가 선택했을 때
  const handleSelectPrediction = (prediction) => {
    const fullRecipe = recipes.find(r => r.recipe_id === prediction.recipe_id);
    setSelectedRecipe(fullRecipe);
  };

  // 섭취량을 선택했을 때
  const handleSelectPortion = async (selectedPortion) => {
    setUploading(true); // 계산 중임을 나타내기 위해 uploading 상태 사용
    setError(null);
    setPortion(selectedPortion); // portion 상태 저장

    try {
      const response = await axios.post('http://localhost:8080/api/v1/nutrition/calculate', {
        recipe_id: selectedRecipe.recipe_id,
        portion: selectedPortion
      });
      setFinalNutrition(response.data);
    } catch (error) {
      console.error('영양 정보 계산 중 오류 발생:', error);
      setError('영양 정보 계산에 실패했습니다. 다시 시도해 주세요.');
    } finally {
      setUploading(false);
    }
  };

  // 식단 기록 저장
  const handleSaveLog = async () => {
    if (!selectedRecipe || !portion) return;

    try {
      await axios.post('http://localhost:8080/api/v1/meal-logs/', {
        recipe_id: selectedRecipe.recipe_id,
        portion: portion,
      });
      alert('성공적으로 기록되었습니다!');
      resetAll();
    } catch (error) {
      console.error('식단 기록 저장 중 오류 발생:', error);
      setError('기록 저장에 실패했습니다.');
    }
  };

  // 화면 모드 변경
  const toggleViewMode = () => {
    if (viewMode === 'analysis') {
      fetchMealLogs(); // 식단 일지 데이터를 불러옴
      fetchDailySummary(); // 일일 합계도 함께 불러옴
      setViewMode('log');
    } else {
      setViewMode('analysis');
      resetAll(); // 분석 화면으로 돌아갈 때 초기화
    }
  };

  const resetAll = () => {
    setSelectedFile(null);
    setPreview(null);
    setPredictions([]);
    setSelectedRecipe(null);
    setFinalNutrition(null);
    setError(null);
    setPortion(null);
  }

  return (
    <>
      <header>
        <h1>영유아 영양 관리 솔루션</h1>
        <button onClick={toggleViewMode} className="view-toggle-button">
          {viewMode === 'analysis' ? '식단 기록 보기' : '분석 화면으로 돌아가기'}
        </button>
      </header>

      {viewMode === 'analysis' && (
        <>
          {/* 초기 화면 또는 모든 과정이 끝난 후 */}
          {!selectedFile && !finalNutrition && (
            <div className="upload-section">
              <h2>무엇을 먹었나요? 사진을 올려주세요!</h2>
              <input type="file" accept="image/*" onChange={handleFileChange} />
            </div>
          )}

          {/* 이미지 미리보기 및 분석 버튼 */}
          {selectedFile && !predictions.length && !finalNutrition && (
            <div className="upload-section">
              <h2>무엇을 먹었나요? 사진을 올려주세요!</h2>
              <input type="file" accept="image/*" onChange={handleFileChange} />
              {preview && (
                <div className="image-preview">
                  <img src={preview} alt="선택한 이미지 미리보기" style={{ maxWidth: '300px', marginTop: '10px' }} />
                </div>
              )}
              <button onClick={handleUpload} disabled={uploading}>
                {uploading ? '분석 중...' : '분석하기'}
              </button>
            </div>
          )}

          {error && <p style={{ color: 'red', marginTop: '10px' }}>{error}</p>}

          {/* 예측 결과 표시 */}
          {predictions.length > 0 && !selectedRecipe && (
            <div className="prediction-section">
              <h2>AI 분석 결과</h2>
              <p>이 음식은 아래의 레시피와 가장 유사해 보여요. 실제 만드신 음식을 선택해주세요.</p>
              <div className="card-container">
                {predictions.map((p) => (
                  <button key={p.recipe_id} className="card" onClick={() => handleSelectPrediction(p)}>
                    <h3>{p.recipe_name}</h3>
                    <p>(유사도: {Math.round(p.score * 100)}%)</p>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* 섭취량 선택 */}
          {selectedRecipe && !finalNutrition && (
            <div className="portion-section">
              <h2>{selectedRecipe.recipe_name}</h2>
              <p>아기가 얼마나 먹었나요?</p>
              <button onClick={() => handleSelectPortion(1.0)} disabled={uploading}>
                {uploading ? '계산 중...' : '전부 먹었어요'}
              </button>
              <button onClick={() => handleSelectPortion(0.75)} disabled={uploading}>
                {uploading ? '계산 중...' : '절반 이상 먹었어요'}
              </button>
              <button onClick={() => handleSelectPortion(0.5)} disabled={uploading}>
                {uploading ? '계산 중...' : '절반 정도 먹었어요'}
              </button>
              <button onClick={() => handleSelectPortion(0.25)} disabled={uploading}>
                {uploading ? '계산 중...' : '조금 먹었어요'}
              </button>
            </div>
          )}

          {/* 최종 영양 정보 표시 */}
          {finalNutrition && (
            <div className="nutrition-section">
              <h2>최종 섭취 영양 정보</h2>
              <ul>
                <li>칼로리: {finalNutrition.calories_kcal.toFixed(1)} kcal</li>
                <li>단백질: {finalNutrition.protein_g.toFixed(1)} g</li>
                <li>탄수화물: {finalNutrition.carbs_g.toFixed(1)} g</li>
                <li>지방: {finalNutrition.fat_g.toFixed(1)} g</li>
              </ul>
              <div className="button-group">
                <button onClick={handleSaveLog}>기록 저장하기</button>
                <button onClick={resetAll}>새로 분석하기</button>
              </div>
            </div>
          )}

          <hr />

          <h2>레시피 목록</h2>
          {error && <p style={{ color: 'red' }}>{error}</p>}
          <div className="card-container">
            {recipes.map(recipe => (
              <div key={recipe.recipe_id} className="card">
                <h3>{recipe.recipe_name}</h3>
                <p><strong>분류:</strong> {recipe.category}</p>
                <p>{recipe.description}</p>
              </div>
            ))}
          </div>
        </>
      )}

      {viewMode === 'log' && (
        <div className="meal-log-section">
          <h2>식단 기록</h2>
          {error && <p style={{ color: 'red' }}>{error}</p>}
          {mealLogs.length === 0 && <p>아직 기록된 식단이 없습니다.</p>}
          <div className="log-container">
            {mealLogs.map(log => (
              <div key={log.id} className="log-item card">
                <h3>{log.recipe.recipe_name}</h3>
                <p><strong>섭취 시간:</strong> {new Date(log.meal_time).toLocaleString()}</p>
                <p><strong>섭취량:</strong> {log.portion}인분</p>
                <ul>
                  <li>칼로리: {parseFloat(log.calories_kcal).toFixed(1)} kcal</li>
                  <li>단백질: {parseFloat(log.protein_g).toFixed(1)} g</li>
                  <li>탄수화물: {parseFloat(log.carbs_g).toFixed(1)} g</li>
                  <li>지방: {parseFloat(log.fat_g).toFixed(1)} g</li>
                </ul>
              </div>
            ))}
          </div>

          <h2 style={{ marginTop: '24px' }}>권장 대비 충족률</h2>
          <div className="card" style={{ padding: '12px', marginBottom: '16px' }}>
            <label>
              날짜 선택:
              <input type="date" value={analysisDate} onChange={(e) => setAnalysisDate(e.target.value)} style={{ marginLeft: '8px' }} />
            </label>
            <button onClick={handleAnalyzeDaily} style={{ marginLeft: '12px' }}>분석하기</button>
            {analysisResult && (
              <div className="analysis-card" style={{ marginTop: '12px' }}>
                <h3>{analysisResult.totals.date}</h3>
                <ul>
                  {analysisResult.coverages && analysisResult.coverages.map((c) => (
                    <li key={c.name}>
                      {c.name}: {Number(c.coverage_pct).toFixed(1)}% ({Number(c.total).toFixed(1)}/{c.target} {c.unit}) {c.deficiency ? '부족' : '적정'}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <h2 style={{ marginTop: '24px' }}>일일 영양 합계</h2>
          <div className="log-container">
            {dailySummary.map(day => (
              <div key={day.date} className="log-item card">
                <h3>{day.date}</h3>
                <ul>
                  <li>총 칼로리: {day.total_calories_kcal.toFixed(1)} kcal</li>
                  <li>총 단백질: {day.total_protein_g.toFixed(1)} g</li>
                  <li>총 탄수화물: {day.total_carbs_g.toFixed(1)} g</li>
                  <li>총 지방: {day.total_fat_g.toFixed(1)} g</li>
                </ul>
              </div>
            ))}
          </div>

          <h2 style={{ marginTop: '24px' }}>지식 검색 (RAG)</h2>
          <div className="card" style={{ padding: '12px', marginBottom: '16px' }}>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '8px' }}>
              <input
                type="text"
                value={ragQuery}
                onChange={(e) => setRagQuery(e.target.value)}
                placeholder="예: 6-11개월 단백질 권장량"
                style={{ flex: 1, padding: '8px' }}
              />
              <button onClick={handleRagSearch} disabled={ragLoading}>
                {ragLoading ? '검색 중...' : '검색'}
              </button>
            </div>
            {ragError && <p style={{ color: 'red' }}>{ragError}</p>}
            <div className="log-container">
              {ragAnswer && (
                <div className="rag-answer card" style={{ backgroundColor: '#1e1e1e', borderColor: '#333', marginBottom: '16px', color: '#ffffff' }}>
                  <h3 style={{ color: '#ffffff' }}>✨ AI 요약 답변</h3>
                  <div
                    style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6', fontSize: '1.05em' }}
                    dangerouslySetInnerHTML={{
                      __html: ragAnswer.replace(/\*\*(.*?)\*\*/g, '<strong style="color: #ff4d4d;">$1</strong>')
                    }}
                  />
                </div>
              )}

              {ragResults.length > 0 && <h4 style={{ color: '#555', marginBottom: '8px' }}>참고 문서 출처</h4>}
              {ragResults.map((r, index) => (
                <div key={r.id} className="log-item card" style={{ padding: '12px', marginBottom: '8px', fontSize: '0.9em' }}>
                  <p><strong>[{index + 1}] 출처:</strong> {r.source.split('/').pop()} {r.version ? `(${r.version})` : ''}</p>
                  <p style={{ whiteSpace: 'pre-wrap', color: '#666', marginTop: '4px' }}>
                    {(r.content || '').slice(0, 200)}{(r.content || '').length > 200 ? '...' : ''}
                  </p>
                </div>
              ))}
              {!ragLoading && !ragAnswer && ragResults.length === 0 && (
                <p>검색 결과가 없습니다.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}

export default App
