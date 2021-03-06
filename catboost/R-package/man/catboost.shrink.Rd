% Generated by roxygen2: do not edit by hand
% Please edit documentation in R/catboost.R
\name{catboost.shrink}
\alias{catboost.shrink}
\title{Shrink the model}
\usage{
catboost.shrink(model, ntree_end, ntree_start = 0)
}
\arguments{
\item{ntree_end}{Leave the trees with indices from the interval [ntree_start, ntree_end) (zero-based indexing)..}

\item{ntree_start}{Leave the trees with indices from the interval [ntree_start, ntree_end) (zero-based indexing)..

Default value: 0}
}
\description{
Shrink the model
}
\seealso{
\url{https://tech.yandex.com/catboost/doc/dg/concepts/r-reference_catboost-shrink-docpage/}
}
