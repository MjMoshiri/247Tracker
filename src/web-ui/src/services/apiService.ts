import { DynamoDB } from 'aws-sdk';
import { JobAd } from '../types/JobAd';
import dotenv from 'dotenv';

const dynamoDb = new DynamoDB.DocumentClient({
    region: process.env.REACT_APP_AWS_REGION,
    accessKeyId: process.env.REACT_APP_AWS_ACCESS_KEY_ID,
    secretAccessKey: process.env.REACT_APP_AWS_SECRET_ACCESS_KEY
});

const TABLE_NAME = process.env.REACT_APP_DYNAMODB_TABLE_NAME!!;
const UNPROCESSED_JOBS_INDEX = process.env.REACT_APP_UNPROCESSED_JOBS_INDEX!!;


export const fetchJobs = async (page: number, pageSize: number): Promise<JobAd[]> => {
    try {
        const params = {
            TableName: TABLE_NAME,
            IndexName: UNPROCESSED_JOBS_INDEX,
            KeyConditionExpression: '#processed = :processed',
            ExpressionAttributeNames: {
                '#processed': 'Processed'
            },
            ExpressionAttributeValues: {
                ':processed': "No"
            },
            Limit: pageSize,
            ExclusiveStartKey: page > 1 ? { Processed: false, DateAdded: `page-${page}` } : undefined
        };
        const response = await dynamoDb.query(params).promise();
        return response.Items!!.map(item => ({
            id: item.JobID,
            date_added: item.DateAdded,
            description: item.JobDescription,
            link: item.Link,
            is_qualified: item.IsQualified,
            processed: item.Processed === "Yes",
            title: item.JobTitle,
            company: item.Company,
        })) as JobAd[];        
    } catch (error) {
        console.error('Error fetching unprocessed jobs', error);
        throw error;
    }
};
export const fetchCount = async () => {
    try {
        const params = {
            TableName: TABLE_NAME,
            IndexName: UNPROCESSED_JOBS_INDEX,
            KeyConditionExpression: '#processed = :processed',
            ExpressionAttributeNames: {
                '#processed': 'Processed'
            },
            ExpressionAttributeValues: {
                ':processed': "No"
            },
            Select: 'COUNT'
        };
        const response = await dynamoDb.query(params).promise();
        return response.Count!!;
    } catch (error) {
        console.error('Error fetching job count', error);
        throw error;
    }
};

export const updateJob = async (job: JobAd) => {
    try {
        const params = {
            TableName: TABLE_NAME,
            Key: { 
                JobID: job.id,
                DateAdded: job.date_added
            },
            UpdateExpression: 'set JobTitle = :title, JobDescription = :description, Link = :link, Company = :company, IsQualified = :isQualified, DateProcessed = :dateProcessed, #p = :processed',
            ExpressionAttributeNames: {
                '#p': 'Processed'
            },
            ExpressionAttributeValues: {
                ':title': job.title,
                ':description': job.description,
                ':link': job.link,
                ':company': job.company,
                ':isQualified': job.is_qualified,
                ':dateProcessed': job.date_processed,
                ':processed': "Yes",
            }
        };
        await dynamoDb.update(params).promise();
    } catch (error) {
        console.error('Error updating job application', error);
        throw error;
    }
};