import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D
from tensorflow.keras.models import Model
import os

# 데이터 경로 및 파라미터 설정
DATA_DIR = 'ml/data/images'
IMG_HEIGHT, IMG_WIDTH = 224, 224
BATCH_SIZE = 8 # 가지고 있는 데이터 양이 적으므로 배치 크기를 줄입니다.
EPOCHS = 15    # 에포크 수

def build_and_train_model():
    """
    전이 학습을 사용하여 모델을 구성하고 훈련시킨 후 저장합니다.
    """
    # 1. 데이터 준비 (학습/검증 데이터셋)
    # 데이터 증강(augmentation)을 통해 데이터 양을 늘리고 모델의 일반화 성능을 향상시킵니다.
    datagen = ImageDataGenerator(
        rescale=1./255,
        validation_split=0.2, # 20%를 검증 데이터로 사용
        rotation_range=20,
        width_shift_range=0.2,
        height_shift_range=0.2,
        shear_range=0.2,
        zoom_range=0.2,
        horizontal_flip=True,
        fill_mode='nearest'
    )

    train_generator = datagen.flow_from_directory(
        DATA_DIR,
        target_size=(IMG_HEIGHT, IMG_WIDTH),
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        subset='training'
    )

    validation_generator = datagen.flow_from_directory(
        DATA_DIR,
        target_size=(IMG_HEIGHT, IMG_WIDTH),
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        subset='validation'
    )
    
    # 클래스(음식 종류) 이름과 인덱스 저장
    class_indices = train_generator.class_indices
    print("클래스 정보:", class_indices)
    
    # 클래스 이름을 파일로 저장 (나중에 예측 시 사용)
    output_dir = "ml/model"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    with open(os.path.join(output_dir, 'class_names.txt'), 'w', encoding='utf-8') as f:
        # 딕셔너리의 키(클래스 이름) 순서를 인덱스 기준으로 정렬하여 저장
        sorted_class_names = sorted(class_indices.keys(), key=lambda x: class_indices[x])
        for class_name in sorted_class_names:
            f.write(f"{class_name}\n")


    # 2. 전이 학습 모델 구성 (MobileNetV2 기반)
    base_model = MobileNetV2(weights='imagenet', include_top=False, input_shape=(IMG_HEIGHT, IMG_WIDTH, 3))

    # 사전 훈련된 레이어는 동결 (가중치 업데이트 방지)
    base_model.trainable = False

    # 새로운 분류 레이어 추가
    x = base_model.output
    x = GlobalAveragePooling2D()(x)
    x = Dense(128, activation='relu')(x)
    # 출력 레이어의 노드 수는 클래스 수와 동일해야 함
    predictions_layer = Dense(train_generator.num_classes, activation='softmax')(x)

    model = Model(inputs=base_model.input, outputs=predictions_layer)

    # 3. 모델 컴파일
    model.compile(optimizer='adam',
                  loss='categorical_crossentropy',
                  metrics=['accuracy'])

    print("모델 구성 완료. 훈련을 시작합니다.")

    # 4. 모델 훈련
    history = model.fit(
        train_generator,
        steps_per_epoch=train_generator.samples // BATCH_SIZE,
        validation_data=validation_generator,
        validation_steps=validation_generator.samples // BATCH_SIZE,
        epochs=EPOCHS
    )

    print("모델 훈련 완료.")

    # 5. 모델 저장
    model.save(os.path.join(output_dir, 'food_classifier_model.h5'))
    print(f"훈련된 모델을 {os.path.join(output_dir, 'food_classifier_model.h5')} 에 저장했습니다.")
    
    return history

if __name__ == '__main__':
    build_and_train_model()
