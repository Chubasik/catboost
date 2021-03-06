LIBRARY()



SRCS(
    auc.cpp
    balanced_accuracy.cpp
    brier_score.cpp
    classification_utils.cpp
    dcg.cpp
    hinge_loss.cpp
    kappa.cpp
    metric.cpp
    pfound.cpp
    sample.cpp
)

PEERDIR(
    catboost/libs/helpers
    library/containers/2d_array
    library/threading/local_executor
)

GENERATE_ENUM_SERIALIZATION(metric.h)

END()
